import textwrap

import pandas as pd
from cmdc.datasets import OnConflictNothingBase

BASE_URL = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master"


class Locations(OnConflictNothingBase):
    table_name = "jhu_locations"
    pk = "uid"

    def __init__(self):
        self.url = f"{BASE_URL}/csse_covid_19_data/UID_ISO_FIPS_LookUp_Table.csv"
        pass

    def get(self):
        df = pd.read_csv(self.url)
        df.columns = [x.lower() for x in list(df)]
        df = df.rename(columns=dict(long_="lon"))
        self.df = df
        return df


class DailyReports(OnConflictNothingBase):
    table_name = "jhu_daily_reports"
    pk = "(uid, date)"
    raw_cols = [
        "combined_key",
        "date",
        "date_updated",
        "confirmed",
        "deaths",
        "recovered",
        "active",
    ]
    join_clause = "INNER JOIN data.jhu_locations l on l.combined_key = tt.combined_key"

    @property
    def final_cols(self):
        return ["uid"] + self.raw_cols[1:]

    @property
    def excluded_cols(self):
        return self.raw_cols[2:]

    def get(self, date):
        dt = pd.to_datetime(date)
        _date = pd.to_datetime(dt.strftime("%Y-%m-%d"))
        url = f"{BASE_URL}/csse_covid_19_data/csse_covid_19_daily_reports/{dt:%m-%d-%Y}.csv"
        df = pd.read_csv(url)
        df.columns = [x.lower() for x in list(df)]
        df = df.rename(
            columns={
                "long_": "lon",
                "province/state": "province_state",
                "country/region": "country_region",
                "latitude": "lat",
                "longitude": "lon",
            }
        )
        for c in ["last update", "last_update"]:
            if c in df.columns:
                df = df.rename(columns={c: "date_updated"})
                df["date_updated"] = (
                    pd.to_datetime(df["date_updated"]).dt.tz_localize("UTC")
                )
                break
        else:
            df["date_updated"] = None

        if "combined_key" not in df.columns:
            df["combined_key"] = (
                df["province_state"].fillna("") + ", " +
                df["country_region"].fillna("")
            )

        df["date"] = _date
        self.df = df[self.raw_cols]
        return self.df

    def _insert_query(self, df, table_name, temp_name, pk):
        out = f"""
        INSERT INTO data.{table_name} ({", ".join(self.final_cols)})
        SELECT {", ".join(self.final_cols)}
        from {temp_name} tt
        {self.join_clause}
        ON CONFLICT {pk} DO UPDATE SET
        {",".join([f"{n} = EXCLUDED.{n}" for n in self.excluded_cols])};
        """
        return textwrap.dedent(out)


class DailyReportsUS(DailyReports):
    table_name = "jhu_daily_reports_us"
    pk = "(fips, date)"
    raw_cols = [
        "fips",
        "date",
        "date_updated",
        "confirmed",
        "deaths",
        "recovered",
        "active",
        "incident_rate",
        "people_tested",
        "people_hospitalized",
        "mortality_rate",
        "testing_rate",
        "hospitalization_rate"
    ]
    join_clause = "WHERE fips in (SELECT fips FROM data.us_states)"

    @property
    def final_cols(self):
        return self.raw_cols

    def get(self, date):
        dt = pd.to_datetime(date)
        _date = pd.to_datetime(dt.strftime("%Y-%m-%d"))
        url = f"{BASE_URL}/csse_covid_19_data/csse_covid_19_daily_reports_us/{dt:%m-%d-%Y}.csv"
        df = pd.read_csv(url)
        df.columns = [x.lower() for x in list(df)]
        df = df.rename(
            columns={
                "last_update": "date_updated",
                "long_": "lon", }
        )
        df["date_updated"] = pd.to_datetime(df["date_updated"]
                                            ).dt.tz_localize("UTC")
        df["date"] = _date
        df = df.dropna(subset=["fips"])
        self._df_full = df
        self.df = df[self.raw_cols]
        return self.df
