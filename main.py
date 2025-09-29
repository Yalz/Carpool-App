import pandas as pd
from gqlalchemy import Memgraph

# ─────────────────────────────────────────────────────────────
# STEP 1: Load and Clean CSV
# ─────────────────────────────────────────────────────────────

df = pd.read_csv("test_data.csv", on_bad_lines='warn')

# Normalize names
def normalize(name):
    return str(name).strip().title()

df["Name"] = df["Name"].apply(normalize)

# Map driver preferences
driver_map = {
    "Ja": "yes",
    "Nee": "no",
    "Maakt mij niet uit": "neutral"
}
df["DriverStatus"] = df["Wil je graag driver zijn?"].map(driver_map).fillna("unknown")

# ─────────────────────────────────────────────────────────────
# STEP 2: Filter Carpool Participants
# ─────────────────────────────────────────────────────────────

carpool_column = "Ga je mee met de bus of auto"
group_column = "Geef hier 3 à 4 namen op voor je wagen. (Afhankelijk van welk materiaal jullie willen meenemen.) spreek dit even op voorhand af."

filtered = df[df[carpool_column] == "Ik wil graag met de wagen"].copy()
selected_names = filtered["Name"].dropna().tolist()

# Normalize matched names
df["MatchedNames"] = df[group_column].apply(
    lambda text: [normalize(n) for n in selected_names if pd.notna(text) and n in text]
)
df = df[df["MatchedNames"].str.len() > 0]

# ─────────────────────────────────────────────────────────────
# STEP 3: Deduplicate Person Nodes with Driver Status
# ─────────────────────────────────────────────────────────────

# Group by name and keep first non-"unknown" driver status
# ✅ Use full dataset to preserve all driver responses
person_info = pd.read_csv("test_data.csv")
person_info["Name"] = person_info["Name"].apply(normalize)
person_info["DriverStatus"] = person_info["Wil je graag driver zijn?"].map(driver_map).fillna("unknown")

person_info = person_info.groupby("Name").agg({
    "DriverStatus": lambda x: next((v for v in x if v != "unknown"), "unknown"),
    "Wat is je type wagen?": "first",
    "Welke banden heb je?": "first",
    "Heb je sneeuwkettingen voor je banden?": "first",
    "Welke banden maat heb je?": "first"
}).reset_index()


# ─────────────────────────────────────────────────────────────
# STEP 4: Connect to Memgraph
# ─────────────────────────────────────────────────────────────

mg = Memgraph(host="localhost", port=7687)

# Optional: clear existing graph
mg.execute("MATCH (n) DETACH DELETE n")

# ─────────────────────────────────────────────────────────────
# STEP 5: Create Nodes and Relationships
# ─────────────────────────────────────────────────────────────

# Create Person and Car nodes
for _, row in person_info.iterrows():
    person = normalize(row["Name"])
    driver_status = row["DriverStatus"]

    # Create Person node
    mg.execute("""
        MERGE (p:Person {name: $name})
        SET p.driver_status = $status
    """, {"name": person, "status": driver_status})

    # If driver or neutral, create Car node and connect
    if driver_status in ["yes", "neutral"]:
        car_props = {
            "name": person + "_Car",
            "type": row["Wat is je type wagen?"],
            "tire_type": row["Welke banden heb je?"],
            "snowchain": row["Heb je sneeuwkettingen voor je banden?"],
            "tire_size": row["Welke banden maat heb je?"]
        }

        # Create Car node
        mg.execute("""
            MERGE (c:Car {name: $name})
            SET c.type = $type,
                c.tire_type = $tire_type,
                c.snowchain = $snowchain,
                c.tire_size = $tire_size
        """, car_props)

        # Connect driver to car
        mg.execute("""
            MATCH (p:Person {name: $person}), (c:Car {name: $car})
            MERGE (p)-[:DRIVER]->(c)
        """, {"person": person, "car": car_props["name"]})

# Create RIDES_WITH relationships using full Person objects
for _, row in df.iterrows():
    person = normalize(row["Name"])
    driver_status = row["DriverStatus"]

    # Ensure person node exists with full info
    mg.execute("""
        MERGE (p:Person {name: $name})
        SET p.driver_status = $status
    """, {"name": person, "status": driver_status})

    for friend in row["MatchedNames"]:
        friend = normalize(friend)
        friend_status = person_info.loc[person_info["Name"] == friend, "DriverStatus"].values
        friend_status = friend_status[0] if len(friend_status) > 0 else "unknown"

        # Ensure friend node exists
        mg.execute("""
            MERGE (f:Person {name: $name})
            SET f.driver_status = $status
        """, {"name": friend, "status": friend_status})

        # Create RIDES_WITH relationship
        mg.execute("""
            MATCH (p:Person {name: $person}), (f:Person {name: $friend})
            MERGE (p)-[:RIDES_WITH]->(f)
        """, {"person": person, "friend": friend})


