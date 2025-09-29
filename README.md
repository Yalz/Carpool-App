# Carpool-App
PoC of using Graph databases to provide insight in grouping people for carpooling.

## Requirements

* Docker + Docker Compose
* Poetry + Python

## How to run 

First, start your docker environment

```shell
docker compose up
```

Populate your database based on the test data:

```shell
poetry run python main.py
```

Finally, take a look at the groups by going to your Memgraph Lab query window 

`http://localhost:3000/lab/query?component=query`

And paste this query.


```Cypher
CALL weakly_connected_components.get()
YIELD node, component_id
WITH component_id, collect(node) AS group
WITH component_id, [n IN group WHERE n:Person] AS people,
     [n IN group WHERE n:Car] AS cars
WHERE size(people) >= 3 AND size(people) <= 4 AND size(cars) > 0
RETURN component_id, 'set_buddies' AS group_type, [p IN people | p.name] AS members;

CALL weakly_connected_components.get()
YIELD node, component_id
WITH component_id, collect(node) AS group
WITH component_id, [n IN group WHERE n:Person] AS people,
     [n IN group WHERE n:Car] AS cars
WHERE size(people) > 4 AND size(cars) > 0
RETURN component_id, 'breakup_pool' AS group_type, [p IN people | p.name] AS members;

CALL weakly_connected_components.get()
YIELD node, component_id
WITH component_id, collect(node) AS group
WITH component_id, [n IN group WHERE n:Person] AS people,
     [n IN group WHERE n:Car] AS cars
WHERE size(people) < 3 AND size(cars) > 0
RETURN component_id, 'join_pool' AS group_type, [p IN people | p.name] AS members;

```

Or just take a look at the structure:

```Cypher
MATCH (n)-[r]->(m)
RETURN n, r, m;
```