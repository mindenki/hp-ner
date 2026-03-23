import requests
import time
import json

BASE_URL = "https://harrypotter.fandom.com/api.php"



# –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Category     | Pages  | Sentences | % | Sentences per Page
# Characters   |   80   |   6,000   |40%|       75
# Locations    |   40   |   2,500   |17%|       63
# Creatures    |   35   |   2,000   |13%|       57
# Organizations|   30   |   1,500   |10%|       50
# Artifacts    |   50   |   1,500   |10%|       30
# Spells       |   35   |   1,500   |10%|       42

