import os
import csv
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

data_dir = os.path.join("data", "raw", "uzex_spot_data")

print("--- Inspecting contracts.csv ---")
with open(os.path.join(data_dir, "contracts.csv"), "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    contracts = list(reader)

print(f"Total contracts: {len(contracts)}")
categories = Counter(r['Категория товара'] for r in contracts)
groups = Counter(r['Группа товара'] for r in contracts)
industries = Counter(r['Отрасль промышленности'] for r in contracts)

print(f"Top 5 categories: {categories.most_common(5)}")
print(f"Top 5 groups: {groups.most_common(5)}")
print(f"Top 5 industries: {industries.most_common(5)}")

sample_prods = list({r['Наименование продукта'] for r in contracts})[:10]
print(f"Sample product names: {sample_prods}")

print("\n--- Inspecting participants.csv ---")
with open(os.path.join(data_dir, "participants.csv"), "r", encoding="utf-8") as f:
    participants = list(csv.DictReader(f))
print(f"Total participants: {len(participants)}")
roles = Counter(r['Роль'] for r in participants)
print(f"Roles: {roles}")
sample_parts = [(r['ИНН'], r['Наименование'], r['Регион']) for r in participants[:5]]
print(f"Sample participants: {sample_parts}")

print("\n--- Inspecting brokers.csv ---")
with open(os.path.join(data_dir, "brokers.csv"), "r", encoding="utf-8") as f:
    brokers = list(csv.DictReader(f))
print(f"Total brokers: {len(brokers)}")
sample_brokers = [(r['Код брокера'], r['Наименование']) for r in brokers[:5]]
print(f"Sample brokers: {sample_brokers}")

print("\n--- Inspecting deal values format ---")
with open(os.path.join(data_dir, "deals_2022.csv"), "r", encoding="utf-8") as f:
    for i, r in enumerate(csv.DictReader(f)):
        if i < 3:
            print(f"Deal {r['Номер сделки']}: Qty={r['Количество']}, Lot={r['Лот']}, Sum={r['Сумма сделки']}, Unit={r['Единица измерения']}, StartPrice={r['Стартовая цена']}")
