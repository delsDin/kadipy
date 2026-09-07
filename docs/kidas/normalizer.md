# Normalisation (`kadi.kidas.normalizer`)

`Normalizer` standardise les données vers les référentiels internes de
KadiPy : noms de cultures, noms de marchés, coordonnées GPS, et unités de
mesure.

---

## Initialisation

```python
from kadi.kidas import Normalizer
import pandas as pd

df = pd.read_csv("recoltes_2024.csv")
normalizer = Normalizer(df)
```

---

## Méthodes

### `std_crops(column)`

Traduit les noms locaux de cultures vers les codes standardisés KadiPy.

```python
df = normalizer.std_crops(column="culture")
```

**Exemples de correspondances :**

| Nom local (français/fon/dendi) | Code KadiPy |
|-------------------------------|-------------|
| `"maïs"`, `"maize"`, `"baba"` | `"maize"` |
| `"riz"`, `"rice"`, `"maro"` | `"rice"` |
| `"igname"`, `"yam"`, `"isu"` | `"yam"` |
| `"manioc"`, `"cassava"` | `"cassava"` |
| `"niébé"`, `"cowpea"`, `"ewa"` | `"cowpea"` |
| `"sorgho"`, `"sorghum"`, `"dawa"` | `"sorghum"` |
| `"mil"`, `"millet"` | `"millet"` |
| `"tomate"`, `"tomato"` | `"tomato"` |
| `"oignon"`, `"onion"` | `"onion"` |
| `"soja"`, `"soybean"` | `"soybean"` |

---

### `std_markets(column)`

Traduit les noms de marchés vers les identifiants officiels WFP / OSM.

```python
df = normalizer.std_markets(column="marche")
```

---

### `std_coords(lat_col, lon_col)`

Valide et corrige les coordonnées GPS pour s'assurer qu'elles sont dans les
bornes du Bénin.

```python
df = normalizer.std_coords(lat_col="latitude", lon_col="longitude")
```

---

### `convert_units(value_col, unit_col, target_unit)`

Convertit les quantités vers une unité cible.

```python
# Convertir toutes les quantités en kg
df = normalizer.convert_units(
    value_col="quantite",
    unit_col="unite",
    target_unit="kg",
)
```

---

## Exemple complet

```python
import pandas as pd
from kadi.kidas import Normalizer

df = pd.read_csv("enquete_agriculteurs_locale.csv")

normalizer = Normalizer(df)

df_standardise = (
    normalizer
    .std_crops(column="culture")
    .std_markets(column="commune_marche")
    .std_coords(lat_col="latitude", lon_col="longitude")
    .convert_units(value_col="rendement", unit_col="unite", target_unit="kg")
)

print(df_standardise["culture"].unique())
```

---

## Utilisation dans un pipeline

```python
from kadi.kidas import Pipeline

pipeline = Pipeline()

df, rapport = (
    pipeline
    .load_data("enquete_2024.csv")
    .add_cleaning_step("remove_duplicates")
    .add_normalization_step({
        "crops": "culture",
        "markets": "marche",
        "gps": ["latitude", "longitude"],
    })
    .execute(cache=True)
)
```

---

::: kadi.kidas.normalizer.Normalizer

