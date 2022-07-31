#!/usr/bin/env python3

# Using tutorial: https://jcutrer.com/python/learn-geopandas-plotting-usmaps

#LOGBOOK = 'sample-logbook'
LOGBOOK = '/mnt/jerdocs/Documents/Projects/Flying/Logbook.ods'

AIRPORT_DB = 'data/airport-codes.json'
STATES_SHAPES = 'data/state-shapes/cb_2018_us_state_20m.shp'
DROPPED_STATES = ['HI', 'PR']


import json
import pandas as pd
import geopandas
import sys

class AirportDatabase:
    def __init__(self):
        df = pd.read_json(AIRPORT_DB)
        df = df.set_index('ident')

        # there's probably a better way to do this in a single pass
        # and without copy-pasted code
        df['lon'] = df['coordinates'].apply(lambda c: float(c.split(', ')[0]))
        df['lat'] = df['coordinates'].apply(lambda c: float(c.split(', ')[1]))
    
        self.df = df

    def canonicalize_airport_code(self, code):
        if "K"+code in self.df.index:
            return "K"+code
        if "C"+code in self.df.index:
            return "C"+code
        if code in self.df.index:
            return code

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
        #for i, row in df[df['codes'].isna() & ~df['Route'].isna()].iterrows():
        #    print(row)

        # Drop any lines that don't appear to have a valid route
        df = df[~df['codes'].isna()]

        self.df = df

class Landings:
    def __init__(self, logbook, airport_db):
        # Get a unique list of every airport we've landed at
        landings = set()
        for codes in logbook.df['codes']:
            landings.update(codes)

        df = pd.DataFrame(sorted(landings), columns=['code'])

        # Annotate the landings dataframe with info from the airport info
        # database
        df = df.join(airport_db.df, on='code')
        df = df.set_index('code')

        for idx, landing in df.iterrows():
            if landing['lat'] < 10:
                print(landing)

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
    #states = states.to_crs("EPSG:3395")
    for state in DROPPED_STATES:
        states.drop(states[states['STUSPS'] == state].index, inplace = True)
                       
    return states

def main():
    airport_db = AirportDatabase()
    logbook = Logbook(airport_db)
    landings = Landings(logbook, airport_db)

    # Get the list of unique states in which we've landed
    landing_state_codes = get_landing_state_codes(landings)
    print(f"{len(landing_state_codes)} unique states: {sorted(landing_state_codes)}")

    # Plot state boundaries
    state_shapes = get_state_shapes()
    ax = state_shapes.boundary.plot(figsize=(30, 17), color="Black")

    # Plot landing states in green
    state_shapes[state_shapes['STUSPS'].isin(landing_state_codes)].plot(
        ax=ax,
        color='Green')

    # Plot non-landing states in light grey
    state_shapes[~state_shapes['STUSPS'].isin(landing_state_codes)].plot(
        ax=ax,
        color='LightGrey')

    # Plot routes between airports
    for idx, flight in logbook.df.iterrows():
        routecodes = flight['codes']
        for i in range(len(routecodes)-1):
            from_airport = airport_db.df.loc[routecodes[i]]
            to_airport = airport_db.df.loc[routecodes[i+1]]
            x = [from_airport['lon'], to_airport['lon']]
            y = [from_airport['lat'], to_airport['lat']]
            ax.plot(x, y, color='blue')

    # Plot airports with landings
    landings.df.plot.scatter(ax=ax, x='lon', y='lat', color='red', zorder=5)

    ax.set_axis_off()
    ax.set_xlim([-170, -65])
    ax.set_ylim([25, 73.5])
    ax.figure.tight_layout()
    ax.figure.savefig("/home/jelson/public_html/fig.png")
    ax.figure.savefig("/home/jelson/public_html/fig.svg")

main()