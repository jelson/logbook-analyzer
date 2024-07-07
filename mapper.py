#!/usr/bin/env python3

# Using tutorial: https://jcutrer.com/python/learn-geopandas-plotting-usmaps

import geopandas
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

# don't attempt to connect over X11 when creating a plot
matplotlib.use('Agg')

LOGBOOK = '/mnt/jerdocs/Documents/Projects/Flying/Logbook.ods'

AIRPORT_DB = 'data/airport-codes.json'
STATES_SHAPES = 'data/state-shapes/cb_2018_us_state_20m.shp'
DROPPED_STATES = ['HI', 'PR']
CANADA_SHAPES = 'data/canada-shapes/canada.shp'
DRAWN_PROVINCES = ['B.C.', 'Y.T.']
MERCATOR_CRS = 'EPSG:3395'


class AirportDatabase:
    def __init__(self):
        df = pd.read_json(AIRPORT_DB)

        # Drop all airports that are not in North America
        df = df[df['continent'] == 'NA']

        # Set index to be the airport's globally unique identifier
        df = df.set_index('ident')

        # Convert the 'coordinates' field, which is a string that looks like
        # "-144.5, 44.5", to float lats and lons
        lonlat = df['coordinates'].str.split(', ', expand=True).astype(float)

        # Make it into a geodataframe so we can do coordinate reference system
        # conversions
        gdf = geopandas.GeoDataFrame(
            df,
            geometry=geopandas.points_from_xy(
                x=lonlat[0], y=lonlat[1],
                crs=4326,
            )
        )

        # Convert to mercator
        gdf = gdf.to_crs(MERCATOR_CRS)

        self.df = gdf

    # Determine the canonical identifier of an airport code in the logbook
    def canonicalize_airport_code(self, code):
        if "K"+code in self.df.index:
            return "K"+code
        if "C"+code in self.df.index:
            return "C"+code
        if code in self.df.index:
            return code
        local = self.df[self.df['local_code'] == code]
        if len(local) == 1:
            return local.index[0]

        print(f"Unknown airport: {code}")
        return None

    # Split apart strings such as "KSMO-KRNT". Cheesy heuristic to
    # see if the route text is actually a route or not.
    def split_valid_route(self, route):
        if not isinstance(route, str):
            return None

        codes = route.strip().split('-')

        # Use a cheesy heuristic to reject lines that are not actually a
        # route, e.g. a text line like "Annual inspection"
        if len(codes) < 2 or len(codes) > 9:
            return None

        # More cheesy heuristics: ensure every code is either 3 or 4
        # characters
        for code in codes:
            if len(code) != 3 and len(code) != 4:
                return None

        # Canonicalize each airport code
        codes = [self.canonicalize_airport_code(code) for code in codes]

        # Invalidate the whole route if it contains an invalid
        # airport. Not sure if this is the right policy.
        if None in codes:
            return None

        return codes


# Get my logbook as a dataframe
class Logbook:
    def __init__(self, airport_db):
        # Read the logbook spreadsheet in as a dataframe
        df = pd.read_excel(LOGBOOK, engine='odf', header=1)

        # Try to find "real" routes, and split them apart into separate
        # codes if they appear to be valid
        df['codes'] = df['Route'].apply(airport_db.split_valid_route)

        # Report errors
        if False:
            for i, row in df[df['codes'].isna() & ~df['Route'].isna()].iterrows():
                print(row)

        # Drop any lines that don't appear to have a valid route
        df = df[~df['codes'].isna()]

        self.df = df


class Landings:
    def __init__(self, logbook, airport_db):
        # Get a unique list of every airport we've landed at
        landing_airports = set([airport for route in logbook.df['codes'] for airport in route])

        df = airport_db.df.loc[sorted(landing_airports)]
        self.df = df


def get_landing_state_codes(landings):
    # Get a unique list of regions we've landed in
    regions = set(landings.df['iso_region'])

    # Convert region list to US states
    states = set()
    for region in regions:
        if region.startswith("US-"):
            states.add(region[3:])

    return states


def get_state_shapes():
    states = geopandas.read_file(STATES_SHAPES)
    states = states.to_crs(MERCATOR_CRS)
    states = states[~states['STUSPS'].isin(DROPPED_STATES)]
    return states


def get_canada_shapes():
    canada = geopandas.read_file(CANADA_SHAPES)
    canada = canada.to_crs(MERCATOR_CRS)
    canada = canada[canada['PREABBR'].isin(DRAWN_PROVINCES)]
    return canada


def main():
    airport_db = AirportDatabase()
    logbook = Logbook(airport_db)
    landings = Landings(logbook, airport_db)
    print(logbook.df)
    print(landings.df)

    # Get the list of unique states in which we've landed
    landing_state_codes = get_landing_state_codes(landings)
    print(f"{len(landing_state_codes)} unique states: {sorted(landing_state_codes)}")

    fig, ax = plt.subplots(figsize=(30, 21))

    # Plot state and province boundaries
    state_shapes = get_state_shapes()
    state_shapes.boundary.plot(ax=ax, color="Black")
    canada_shapes = get_canada_shapes()
    canada_shapes.boundary.plot(ax=ax, color="Black")

    # Plot landing states in green (and all canadian provinces)
    state_shapes[state_shapes['STUSPS'].isin(landing_state_codes)].plot(
        ax=ax,
        color='Green')
    canada_shapes.plot(
        ax=ax,
        color='Green')

    # Plot non-landing states in light grey
    state_shapes[~state_shapes['STUSPS'].isin(landing_state_codes)].plot(
        ax=ax,
        color='LightGrey')

    # Plot routes between airports
    for routecodes in logbook.df['codes']:
        for i in range(len(routecodes)-1):
            from_coord = airport_db.df.loc[routecodes[i]]['geometry']
            to_coord = airport_db.df.loc[routecodes[i+1]]['geometry']
            x = [from_coord.x, to_coord.x]
            y = [from_coord.y, to_coord.y]
            ax.plot(x, y, color='blue')

    # Plot airports with landings
    #ax.plot(x=[p.x for p in landings.df['geometry']],
    #        y=[p.y for p in landings.df['geometry']],
    #        color='red',
    #        marker='o',
    #        )
    landings.df.plot(ax=ax, color='red', marker='o', zorder=5)
    landings.df['geometry'].plot(ax=ax, color='red', zorder=5)

    ax.set_axis_off()
    ax.set_xlim([-1.8e7, -0.74e7])
    ax.set_ylim([.25e7, 1e7])
    ax.figure.tight_layout()
    ax.figure.savefig("/home/jelson/public_html/landings.png")
    ax.figure.savefig("/home/jelson/public_html/landings.svg")


if __name__ == "__main__":
    main()
