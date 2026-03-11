"""
Author: Alexander Mackey
Student ID: C22739165
Description: Management command to scrape real departure flight data from AviationStack API
             and populate the Flight model. Supports three AviationStack endpoints, selected
             automatically based on how far ahead the target date is.

Endpoint Strategy:
    delta = (target_date - date.today()).days
    delta <= 0  → /v1/flights        Real-time + historical data
    delta 1-6   → /v1/routes         Scheduled routes (no date filter, time only)
    delta 7+    → /v1/flightsFuture  Future schedule (different schema, real aircraft data)

Usage:
    python manage.py scrape_flights                              # Today, DUB
    python manage.py scrape_flights --date 2026-03-12            # Near-future (routes)
    python manage.py scrape_flights --date 2026-03-20            # Far-future (flightsFuture)
    python manage.py scrape_flights --airport DUB ORK SNN        # All airports
    python manage.py scrape_flights --clear                      # Clear before import
    python manage.py scrape_flights --date 2026-03-10 --clear    # Clear + re-scrape

AviationStack API:
    - Basic tier: HTTPS, 10,000 requests/month
    - Docs: https://aviationstack.com/documentation
"""

import os
import time
import requests

from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import Point
from django.utils import timezone

from core.models import Airport, AircraftType, Flight


# ---------------------------------------------------------------------------
# AIRLINE-BASED AIRCRAFT HEURISTICS
# AviationStack returns aircraft.iata = None on /v1/flights for all tiers.
# /v1/routes has no aircraft data at all.
# /v1/flightsFuture has real aircraft.modelCode — heuristics only used as fallback.
#
# Key: airline IATA code (2-letter, lowercase). Value: AircraftType.model in DB.
# ---------------------------------------------------------------------------
AIRLINE_AIRCRAFT_MAP = {
    # Ryanair — all-737 fleet
    'fr': 'B737-800',
    # Aer Lingus narrow-body Europe (transatlantic overridden per-flight below)
    'ei': 'A320',
    # British Airways
    'ba': 'A319',
    # Lufthansa Group
    'lh': 'A320',
    'lx': 'A320',        # Swiss
    'os': 'A320',        # Austrian
    'sn': 'A320',        # Brussels Airlines
    # Other European short-haul
    'vy': 'A320',        # Vueling
    'w6': 'A321',        # Wizz Air
    'u2': 'A320',        # easyJet
    'ls': 'B737-800',    # Jet2
    'by': 'B737-800',    # TUI
    'to': 'B737-800',    # Transavia
    'ay': 'A320',        # Finnair
    'tp': 'A320',        # TAP
    'ib': 'A320',        # Iberia
    'vl': 'A320',        # Volotea
    # Long-haul carriers serving DUB
    'ek': 'B777-300ER',  # Emirates
    'qr': 'B787-9',      # Qatar Airways
    'aa': 'B787-9',      # American Airlines
    'dl': 'B787-9',      # Delta
    'ua': 'B787-9',      # United
    'ac': 'B787-9',      # Air Canada
    # Regional
    're': 'ATR-72',      # Stobart Air / Aer Arann
}

# Destinations that indicate Aer Lingus wide-body (A330-300) operation.
# Used to override the default 'ei' → A320 mapping.
TRANSATLANTIC_DESTINATIONS = {
    'JFK', 'BOS', 'ORD', 'LAX', 'SFO', 'SEA', 'MIA', 'IAD', 'EWR',
    'PHL', 'ATL', 'MSP', 'MCO', 'CLE', 'IND', 'BNA', 'BDL',
    'YYZ', 'YUL', 'YVR', 'YEG',
}

# PostGIS requires a valid Point for every Airport record.
# Unknown destination airports get (0, 0) as a sentinel — EstimationService
# only uses the origin airport's location, so this is harmless.
UNKNOWN_AIRPORT_LOCATION = Point(0.0, 0.0, srid=4326)


class Command(BaseCommand):
    """
    Fetches real departure flight data from AviationStack API and stores
    it in the Flight model. Automatically selects the correct endpoint
    based on how far ahead the target date is:

        Today / historical  → /v1/flights
        1–6 days ahead      → /v1/routes
        7+ days ahead       → /v1/flightsFuture

    Each endpoint returns a different schema, so each has its own
    _process_*() method. All three ultimately upsert into the same
    Flight model with the same fields.
    """

    help = 'Scrape real departure flights from AviationStack API into the Flight model'

    # AviationStack returns max 100 records per page. We paginate until done.
    PAGE_SIZE = 100

    def add_arguments(self, parser):
        parser.add_argument(
            '--airport',
            nargs='+',
            default=['DUB'],
            metavar='IATA',
            help='Airport IATA code(s) to scrape (default: DUB). Example: --airport DUB ORK SNN'
        )
        parser.add_argument(
            '--date',
            default=None,
            metavar='YYYY-MM-DD',
            help='Date to scrape flights for (default: today). Example: --date 2026-03-20'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing flights for the target airport(s) and date before importing'
        )

    def handle(self, *args, **options):
        """
        Main entry point. Reads API key, resolves target date, then
        delegates to _scrape_airport() for each requested airport.
        """
        api_key = os.environ.get('AVIATIONSTACK_API_KEY')
        if not api_key:
            raise CommandError(
                'AVIATIONSTACK_API_KEY not found in environment. '
                'Add it to your .env file and restart the server.'
            )

        airports = [code.upper() for code in options['airport']]

        # Parse --date or default to today
        if options['date']:
            try:
                target_date = date.fromisoformat(options['date'])
            except ValueError:
                raise CommandError(
                    f"Invalid date format: '{options['date']}'. Use YYYY-MM-DD."
                )
        else:
            target_date = date.today()

        # Determine which endpoint will be used — purely for the log header
        delta = (target_date - date.today()).days
        if delta <= 0:
            endpoint_label = '/v1/flights (real-time / historical)'
        elif delta <= 6:
            endpoint_label = '/v1/routes (near-future schedule)'
        else:
            endpoint_label = '/v1/flightsFuture (7+ day schedule)'

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✈  AirFlow Flight Scraper — {target_date.strftime("%A %d %B %Y")}'
            )
        )
        self.stdout.write(f'   Airports : {", ".join(airports)}')
        self.stdout.write(f'   Endpoint : {endpoint_label}\n')

        total_created = 0
        total_updated = 0

        for iata_code in airports:
            created, updated = self._scrape_airport(
                api_key=api_key,
                iata_code=iata_code,
                target_date=target_date,
                clear=options['clear'],
            )
            total_created += created
            total_updated += updated

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Done — {total_created} flights created, {total_updated} updated.\n'
            )
        )

    # ------------------------------------------------------------------
    # ORCHESTRATION
    # ------------------------------------------------------------------

    def _scrape_airport(
        self,
        api_key: str,
        iata_code: str,
        target_date: date,
        clear: bool,
    ) -> tuple[int, int]:
        """
        Fetch all departures for a single airport and upsert into DB.
        Routes to the correct endpoint + processor based on date delta.

        Args:
            api_key:     AviationStack access key
            iata_code:   IATA airport code to scrape departures for
            target_date: Date being scraped
            clear:       If True, delete existing flights for this airport/date first

        Returns:
            Tuple of (created_count, updated_count)
        """
        self.stdout.write(f'\n--- {iata_code} ---')

        try:
            origin_airport = Airport.objects.get(iata_code=iata_code)
        except Airport.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f'  ✗ Airport {iata_code} not found in database. '
                    f'Run load_reference_data first.'
                )
            )
            return 0, 0

        if clear:
            deleted, _ = Flight.objects.filter(
                origin=origin_airport,
                departure_time__date=target_date,
            ).delete()
            self.stdout.write(f'  Cleared {deleted} existing flights for {iata_code} on {target_date}.')

        # -------------------------------------------------------------------
        # ENDPOINT ROUTING
        # Select fetch method and process method based on date delta.
        # This is the core of Phase 4B — the same scraper handles all three
        # AviationStack endpoints transparently from the caller's perspective.
        # -------------------------------------------------------------------
        delta = (target_date - date.today()).days

        if delta <= 0:
            # Today or historical — real-time data with full status info
            all_flights = self._fetch_all_pages(api_key, iata_code, target_date)
            processor = self._process_flight

        elif delta <= 6:
            # 1–6 days ahead — use scheduled routes as a proxy.
            # /v1/routes has no date filter; we just assign target_date to each record.
            all_flights = self._fetch_routes(api_key, iata_code)
            processor = self._process_route_flight

        else:
            # 7+ days ahead — future schedule endpoint with real aircraft data
            all_flights = self._fetch_future_flights(api_key, iata_code, target_date)
            processor = self._process_future_flight

        if not all_flights:
            self.stdout.write(self.style.WARNING(f'  ⚠ No flights returned for {iata_code}.'))
            return 0, 0

        self.stdout.write(f'  Fetched {len(all_flights)} raw records from API.')

        created = updated = skipped = 0

        for raw in all_flights:
            result = processor(raw, origin_airport, target_date)
            if result == 'created':
                created += 1
            elif result == 'updated':
                updated += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'  ✓ {iata_code}: {created} created, {updated} updated, {skipped} skipped.'
            )
        )
        return created, updated

    # ------------------------------------------------------------------
    # FETCH METHODS  (one per AviationStack endpoint)
    # ------------------------------------------------------------------

    def _fetch_all_pages(self, api_key: str, iata_code: str, target_date: date) -> list[dict]:
        """
        Paginate through /v1/flights for today or a historical date.

        Uses flight_date param (Basic tier feature) to filter by date.
        Paginates with offset until a page comes back with fewer than
        PAGE_SIZE records, meaning we've hit the end.

        Args:
            api_key:     AviationStack access key
            iata_code:   Departure airport IATA code
            target_date: Date to fetch (today or past)

        Returns:
            List of raw flight dicts
        """
        all_records = []
        offset = 0

        while True:
            params = {
                'access_key':  api_key,
                'dep_iata':    iata_code,
                'flight_type': 'departure',
                'flight_date': target_date.isoformat(),
                'limit':       self.PAGE_SIZE,
                'offset':      offset,
            }

            self.stdout.write(f'  Fetching /v1/flights offset={offset}...', ending='')

            try:
                response = requests.get(
                    'https://api.aviationstack.com/v1/flights',
                    params=params,
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as exc:
                self.stdout.write(self.style.ERROR(f' FAILED: {exc}'))
                break

            records = data.get('data') or []
            self.stdout.write(f' {len(records)} records.')

            if not records:
                break

            all_records.extend(records)

            if len(records) < self.PAGE_SIZE:
                break

            offset += self.PAGE_SIZE
            time.sleep(0.5)

        return all_records

    def _fetch_routes(self, api_key: str, iata_code: str) -> list[dict]:
        """
        Paginate through /v1/routes for near-future dates (1–6 days ahead).

        /v1/routes has no date filter — it returns all scheduled routes for
        an airport (the regular weekly timetable). We use it as a proxy for
        any date in the 1–6 day window since Dublin's schedule is highly
        repetitive. The caller assigns target_date to each record's datetime.

        Args:
            api_key:   AviationStack access key
            iata_code: Departure airport IATA code

        Returns:
            List of raw route dicts
        """
        all_records = []
        offset = 0

        while True:
            params = {
                'access_key': api_key,
                'dep_iata':   iata_code,
                'limit':      self.PAGE_SIZE,
                'offset':     offset,
            }

            self.stdout.write(f'  Fetching /v1/routes offset={offset}...', ending='')

            try:
                response = requests.get(
                    'https://api.aviationstack.com/v1/routes',
                    params=params,
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as exc:
                self.stdout.write(self.style.ERROR(f' FAILED: {exc}'))
                break

            records = data.get('data') or []
            self.stdout.write(f' {len(records)} records.')

            if not records:
                break

            all_records.extend(records)

            if len(records) < self.PAGE_SIZE:
                break

            offset += self.PAGE_SIZE
            time.sleep(0.5)

        return all_records

    def _fetch_future_flights(
        self, api_key: str, iata_code: str, target_date: date
    ) -> list[dict]:
        """
        Paginate through /v1/flightsFuture for dates 7+ days ahead.

        Note: AviationStack returns offset=None (not 0) in the pagination
        block for this endpoint — we track offset ourselves rather than
        reading it back from the response.

        Note: The API returns a validation_error if date < today + 7.
        _scrape_airport() only calls this method when delta >= 7, so
        we should never hit that error in normal use.

        Args:
            api_key:     AviationStack access key
            iata_code:   Departure airport IATA code
            target_date: Future date (must be >= today + 7)

        Returns:
            List of raw future flight dicts
        """
        all_records = []
        offset = 0

        while True:
            params = {
                'access_key': api_key,
                'iataCode':   iata_code,     # Different param name to /v1/flights
                'type':       'departure',
                'date':       target_date.isoformat(),
                'limit':      self.PAGE_SIZE,
                'offset':     offset,
            }

            self.stdout.write(f'  Fetching /v1/flightsFuture offset={offset}...', ending='')

            try:
                response = requests.get(
                    'https://api.aviationstack.com/v1/flightsFuture',
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as exc:
                self.stdout.write(self.style.ERROR(f' FAILED: {exc}'))
                break

            # Check for API-level errors (e.g. date too close)
            if 'error' in data:
                error_msg = data['error'].get('message', 'Unknown API error')
                self.stdout.write(self.style.ERROR(f' API ERROR: {error_msg}'))
                break

            records = data.get('data') or []
            self.stdout.write(f' {len(records)} records.')

            if not records:
                break

            all_records.extend(records)

            if len(records) < self.PAGE_SIZE:
                break

            # offset is returned as None by this endpoint — track it ourselves.
            # /v1/flightsFuture enforces a per-minute rate limit more aggressively
            # than /v1/flights. 10 seconds between pages keeps us safely under it.
            offset += self.PAGE_SIZE
            time.sleep(10)

        return all_records

    # ------------------------------------------------------------------
    # PROCESS METHODS  (one per AviationStack endpoint schema)
    # ------------------------------------------------------------------

    def _process_flight(
        self,
        raw: dict,
        origin_airport: Airport,
        target_date: date,
    ) -> str:
        """
        Parse a single /v1/flights record and upsert into Flight model.

        Schema used by today / historical endpoint:
            flight.iata         — flight number (e.g. 'FR1234')
            airline.iata        — airline code (e.g. 'FR')
            departure.scheduled — ISO 8601 datetime
            arrival.scheduled   — ISO 8601 datetime
            flight_status       — 'scheduled', 'active', 'landed', etc.
            flight.codeshared   — present if codeshare (skip these)

        Args:
            raw:            Raw dict from /v1/flights API response
            origin_airport: Origin Airport model instance
            target_date:    Date being scraped (used for upsert key)

        Returns:
            'created', 'updated', or 'skipped'
        """
        departure = raw.get('departure') or {}
        arrival   = raw.get('arrival')   or {}
        flight    = raw.get('flight')    or {}
        airline   = raw.get('airline')   or {}

        flight_number = flight.get('iata') or flight.get('number')
        if not flight_number:
            return 'skipped'

        # Skip codeshared flights — same physical aircraft listed under partner
        # airline codes. Keeping only the operating carrier prevents passenger
        # counts from being multiplied 3-5x per departure.
        if flight.get('codeshared') is not None:
            return 'skipped'

        api_status = (raw.get('flight_status') or '').lower()
        status = self._map_status(api_status)

        if status == 'cancelled':
            return 'skipped'

        departure_time = self._parse_datetime(
            departure.get('scheduled') or departure.get('estimated')
        )
        if departure_time is None:
            return 'skipped'

        arrival_time = self._parse_datetime(
            arrival.get('scheduled') or arrival.get('estimated')
        )
        if arrival_time is None:
            arrival_time = departure_time + timedelta(hours=2)

        # aircraft.iata = None on all tiers — use airline heuristic
        airline_iata = (airline.get('iata') or '').lower()
        dest_iata    = (arrival.get('iata') or '').upper()
        aircraft_type = self._resolve_aircraft_type(airline_iata, dest_iata)

        destination_airport = self._get_or_create_airport(dest_iata, arrival)
        airline_name        = airline.get('name') or 'Unknown'
        terminal            = departure.get('terminal') or None
        gate                = departure.get('gate') or None

        flight_obj, created = Flight.objects.update_or_create(
            flight_number=flight_number,
            departure_time__date=target_date,
            origin=origin_airport,
            defaults={
                'destination':    destination_airport,
                'departure_time': departure_time,
                'arrival_time':   arrival_time,
                'aircraft_type':  aircraft_type,
                'airline':        airline_name,
                'terminal':       terminal,
                'gate':           gate,
                'status':         status,
            }
        )

        return 'created' if created else 'updated'

    def _process_route_flight(
        self,
        raw: dict,
        origin_airport: Airport,
        target_date: date,
    ) -> str:
        """
        Parse a single /v1/routes record and upsert into Flight model.

        Schema differences from /v1/flights:
            flight.number       — number only, no flight.iata (build as airline.iata + number)
            airline.iata        — same as /v1/flights
            departure.time      — 'HH:MM:SS' only, no date (combine with target_date)
            arrival.time        — 'HH:MM:SS' only, no date
            No codeshared field — routes are always operating carrier, no dedup needed
            No flight_status    — always treat as 'scheduled'
            No aircraft data    — use airline heuristic

        Args:
            raw:            Raw dict from /v1/routes API response
            origin_airport: Origin Airport model instance
            target_date:    Date to assign to this route's departure time

        Returns:
            'created', 'updated', or 'skipped'
        """
        departure = raw.get('departure') or {}
        arrival   = raw.get('arrival')   or {}
        flight    = raw.get('flight')    or {}
        airline   = raw.get('airline')   or {}

        # /v1/routes has no flight.iata — build flight number from airline code + number
        airline_iata  = (airline.get('iata') or '').upper()
        flight_number_raw = flight.get('number') or ''
        if not airline_iata or not flight_number_raw:
            return 'skipped'

        flight_number = f'{airline_iata}{flight_number_raw}'

        # Build departure datetime by combining target_date with the time string
        departure_time = self._build_datetime_from_time_str(
            target_date, departure.get('time')
        )
        if departure_time is None:
            return 'skipped'

        # Build arrival datetime the same way
        arrival_time = self._build_datetime_from_time_str(
            target_date, arrival.get('time')
        )
        if arrival_time is None:
            # Fallback: assume 2-hour flight
            arrival_time = departure_time + timedelta(hours=2)

        # If arrival appears to be before departure, it crosses midnight — add a day
        if arrival_time <= departure_time:
            arrival_time += timedelta(days=1)

        dest_iata     = (arrival.get('iata') or '').upper()
        aircraft_type = self._resolve_aircraft_type(airline_iata.lower(), dest_iata)

        destination_airport = self._get_or_create_airport(dest_iata, arrival)
        airline_name        = airline.get('name') or 'Unknown'
        terminal            = departure.get('terminal') or None

        # /v1/routes does not include gate — leave as None
        flight_obj, created = Flight.objects.update_or_create(
            flight_number=flight_number,
            departure_time__date=target_date,
            origin=origin_airport,
            defaults={
                'destination':    destination_airport,
                'departure_time': departure_time,
                'arrival_time':   arrival_time,
                'aircraft_type':  aircraft_type,
                'airline':        airline_name,
                'terminal':       terminal,
                'gate':           None,
                'status':         'scheduled',
            }
        )

        return 'created' if created else 'updated'

    def _process_future_flight(
        self,
        raw: dict,
        origin_airport: Airport,
        target_date: date,
    ) -> str:
        """
        Parse a single /v1/flightsFuture record and upsert into Flight model.

        Schema differences from /v1/flights:
            flight.iataNumber       — flight number (not flight.iata)
            airline.iataCode        — airline code (not airline.iata)
            departure.scheduledTime — 'HH:MM' only, no date (combine with target_date)
            arrival.scheduledTime   — 'HH:MM' only, no date
            aircraft.modelCode      — real data e.g. 'a320' (map directly, skip heuristic)
            codeshared              — top-level key (not nested under flight)

        Args:
            raw:            Raw dict from /v1/flightsFuture API response
            origin_airport: Origin Airport model instance
            target_date:    Date being scraped (7+ days ahead)

        Returns:
            'created', 'updated', or 'skipped'
        """
        departure = raw.get('departure') or {}
        arrival   = raw.get('arrival')   or {}
        flight    = raw.get('flight')    or {}
        airline   = raw.get('airline')   or {}
        aircraft  = raw.get('aircraft')  or {}

        # Different field name: flight.iataNumber not flight.iata
        flight_number = flight.get('iataNumber') or flight.get('number')
        if not flight_number:
            return 'skipped'

        # Codeshare check is top-level in this endpoint (not nested under flight)
        if raw.get('codeshared') is not None:
            return 'skipped'

        # Build departure datetime — scheduledTime is 'HH:MM' with no date
        departure_time = self._build_datetime_from_time_str(
            target_date, departure.get('scheduledTime')
        )
        if departure_time is None:
            return 'skipped'

        arrival_time = self._build_datetime_from_time_str(
            target_date, arrival.get('scheduledTime')
        )
        if arrival_time is None:
            arrival_time = departure_time + timedelta(hours=2)

        if arrival_time <= departure_time:
            arrival_time += timedelta(days=1)

        # /v1/flightsFuture has real aircraft data — use it directly
        # model_code is lowercase e.g. 'a320', 'b737' — look up by model name
        model_code = (aircraft.get('modelCode') or '').lower()
        aircraft_type = self._resolve_aircraft_type_from_model(model_code)

        # Fall back to airline heuristic only if model lookup fails
        if aircraft_type is None:
            airline_iata = (airline.get('iataCode') or '').lower()
            dest_iata    = (arrival.get('iataCode') or '').upper()
            aircraft_type = self._resolve_aircraft_type(airline_iata, dest_iata)

        # Different field name: airline.iataCode not airline.iata
        dest_iata    = (arrival.get('iataCode') or '').upper()
        airline_name = airline.get('name') or 'Unknown'

        destination_airport = self._get_or_create_airport(dest_iata, arrival)
        terminal            = departure.get('terminal') or None
        gate                = departure.get('gate') or None

        flight_obj, created = Flight.objects.update_or_create(
            flight_number=flight_number,
            departure_time__date=target_date,
            origin=origin_airport,
            defaults={
                'destination':    destination_airport,
                'departure_time': departure_time,
                'arrival_time':   arrival_time,
                'aircraft_type':  aircraft_type,
                'airline':        airline_name,
                'terminal':       terminal,
                'gate':           gate,
                'status':         'scheduled',
            }
        )

        return 'created' if created else 'updated'

    # ------------------------------------------------------------------
    # HELPER METHODS
    # ------------------------------------------------------------------

    def _build_datetime_from_time_str(
        self,
        target_date: date,
        time_str: str | None,
    ) -> datetime | None:
        """
        Combine a date with a time-only string from AviationStack into a
        timezone-aware datetime.

        Used by /v1/routes ('HH:MM:SS') and /v1/flightsFuture ('HH:MM'),
        both of which return only a time component — no date is included.

        Args:
            target_date: The date to attach to this time
            time_str:    Time string in 'HH:MM:SS' or 'HH:MM' format

        Returns:
            Timezone-aware datetime or None if parsing fails
        """
        if not time_str:
            return None

        # Normalise: strip seconds if present, leaving 'HH:MM'
        parts = time_str.strip().split(':')
        if len(parts) < 2:
            return None

        try:
            hour   = int(parts[0])
            minute = int(parts[1])
        except (ValueError, TypeError):
            return None

        dt = datetime(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
            hour=hour,
            minute=minute,
            second=0,
        )

        return timezone.make_aware(dt)

    def _resolve_aircraft_type_from_model(self, model_code: str) -> 'AircraftType | None':
        """
        Look up an AircraftType directly from a model code string.

        Used for /v1/flightsFuture which provides real aircraft.modelCode
        data (e.g. 'a320', 'b737'). We normalise the code and attempt a
        case-insensitive match against AircraftType.model in the DB.

        Args:
            model_code: Lowercase model string from API e.g. 'a320', 'b738'

        Returns:
            AircraftType instance or None if not found
        """
        if not model_code:
            return None

        # Map common AviationStack modelCode values to our DB model names.
        # AviationStack uses short ICAO-style codes; our DB uses display names.
        model_code_map = {
            'a319': 'A319',
            'a320': 'A320',
            'a321': 'A321',
            'a332': 'A330-300',
            'a333': 'A330-300',
            'b737': 'B737-800',
            'b738': 'B737-800',
            'b739': 'B737-800',
            'b788': 'B787-9',
            'b789': 'B787-9',
            'b77w': 'B777-300ER',
            'b773': 'B777-300ER',
            'at72': 'ATR-72',
            'atr7': 'ATR-72',
        }

        db_model_name = model_code_map.get(model_code.lower())
        if not db_model_name:
            return None

        try:
            return AircraftType.objects.get(model=db_model_name)
        except AircraftType.DoesNotExist:
            return None

    def _get_or_create_airport(self, iata_code: str | None, arrival: dict) -> Airport:
        """
        Return Airport instance for destination. Creates a minimal placeholder
        record if the airport doesn't exist in our DB yet.

        We use (0, 0) as the PostGIS point for unknown airports — this is a
        sentinel value that EstimationService ignores (it only needs origin).

        Args:
            iata_code: Destination airport IATA code (may be None or empty)
            arrival:   Raw arrival dict from AviationStack (for airport name)

        Returns:
            Airport instance (existing or newly created placeholder)
        """
        if not iata_code:
            iata_code = 'UNK'

        # arrival dict field for airport name differs by endpoint:
        # /v1/flights uses 'airport', /v1/routes uses 'airport', /v1/flightsFuture uses 'iataCode'
        airport_name = arrival.get('airport') or f'Unknown ({iata_code})'

        airport, created = Airport.objects.get_or_create(
            iata_code=iata_code,
            defaults={
                'name':     airport_name,
                'city':     airport_name,
                'country':  'Unknown',
                'timezone': 'UTC',
                'location': UNKNOWN_AIRPORT_LOCATION,
            }
        )

        if created:
            self.stdout.write(
                self.style.WARNING(f'    + Created placeholder airport: {iata_code}')
            )

        return airport

    def _resolve_aircraft_type(self, airline_iata: str, dest_iata: str) -> 'AircraftType | None':
        """
        Derive aircraft type from airline IATA code and destination.

        Used when the API does not provide aircraft data (/v1/flights, /v1/routes)
        or when /v1/flightsFuture's modelCode lookup fails.

        Special case: Aer Lingus (EI) uses A330-300 on transatlantic routes
        and A320 on everything else.

        Args:
            airline_iata: 2-letter airline IATA code (lowercase), e.g. 'fr', 'ei'
            dest_iata:    Destination IATA code (uppercase), e.g. 'JFK', 'LHR'

        Returns:
            AircraftType instance or None if airline not in heuristic map
        """
        if not airline_iata:
            return None

        if airline_iata == 'ei' and dest_iata.upper() in TRANSATLANTIC_DESTINATIONS:
            model_name = 'A330-300'
        else:
            model_name = AIRLINE_AIRCRAFT_MAP.get(airline_iata)

        if not model_name:
            return None

        try:
            return AircraftType.objects.get(model=model_name)
        except AircraftType.DoesNotExist:
            return None

    @staticmethod
    def _parse_datetime(dt_string: str | None) -> datetime | None:
        """
        Parse an ISO 8601 datetime string from AviationStack into a
        timezone-aware Python datetime.

        Used only by /v1/flights which returns full ISO datetimes like
        '2026-03-09T06:30:00+00:00'. /v1/routes and /v1/flightsFuture
        return time-only strings handled by _build_datetime_from_time_str().

        Args:
            dt_string: ISO 8601 string or None

        Returns:
            Timezone-aware datetime or None if parsing fails
        """
        if not dt_string:
            return None

        formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(dt_string[:19], fmt[:len(fmt)])
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return dt
            except (ValueError, TypeError):
                continue

        return None

    @staticmethod
    def _map_status(api_status: str) -> str:
        """
        Map AviationStack flight_status string to our Flight.STATUS_CHOICES values.

        Only used for /v1/flights. Routes and future flights are always 'scheduled'.

        Args:
            api_status: Status string from AviationStack (lowercase)

        Returns:
            One of: 'scheduled', 'cancelled', 'delayed', 'departed', 'arrived'
        """
        mapping = {
            'scheduled':  'scheduled',
            'active':     'departed',
            'landed':     'arrived',
            'cancelled':  'cancelled',
            'incident':   'cancelled',
            'diverted':   'departed',
            'delayed':    'delayed',
            'redirected': 'departed',
            'unknown':    'scheduled',
        }
        return mapping.get(api_status, 'scheduled')