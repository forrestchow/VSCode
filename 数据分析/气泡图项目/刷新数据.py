# 修改 Excel 后运行此脚本即可刷新图表数据
# 双击运行 或 在终端执行: python 刷新数据.py

import pandas as pd, json, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Resolve paths relative to this script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
xlsx_path = os.path.join(SCRIPT_DIR, '淘宝食盐类目市场分析.xlsx')
js_path = os.path.join(SCRIPT_DIR, 'bubble_chart_data.js')

df = pd.read_excel(xlsx_path)

plot = pd.DataFrame({
    'brand': df.iloc[:, 5].astype(str),
    'salt_type': df.iloc[:, 7].astype(str),
    'shop': df.iloc[:, 4].astype(str),
    'weight': df.iloc[:, 6],
    'sales': df.iloc[:, 2],
    'unit_price': df.iloc[:, 12],
    'order_price': df.iloc[:, 11],
    'revenue': df.iloc[:, 10],
    'product_id': df.iloc[:, 8],
}).dropna(subset=['sales','unit_price','order_price','revenue'])

def build_sku_str(row_idx):
    parts = []
    for i in range(42):
        spec_col = 15 + i*2
        price_col = 16 + i*2
        if price_col >= len(df.columns): break
        qty = df.iloc[row_idx, spec_col]
        price = df.iloc[row_idx, price_col]
        if pd.notna(qty) and pd.notna(price):
            q = int(qty) if qty == int(qty) else qty
            parts.append((q, price, price/q))
    # Sort by quantity ascending
    parts.sort(key=lambda x: x[0])
    return ';'.join(f'{q}袋|{p:.2f}|{up:.2f}' for q, p, up in parts) if parts else ''

plot['sku_info'] = [build_sku_str(i) for i in plot.index]
plot['weight'] = plot['weight'].fillna(400)
plot = plot[(plot['unit_price'] > 0.5) & (plot['unit_price'] < 80)]
plot = plot[(plot['order_price'] > 1) & (plot['order_price'] < 80)]
plot['brand'] = plot['brand'].replace('nan','其他').replace('无品牌','其他')
plot = plot.sort_values('sales', ascending=False)
plot['rank'] = range(1, len(plot)+1)

total = int(plot['revenue'].sum())  # revenue-based shares
plot['weight_key'] = plot['weight'].astype(int).astype(str)+'g'

salt_sales = plot.groupby('salt_type')['revenue'].sum().sort_values(ascending=False)
salt_shares = [{'salt':st,'sales':int(s),'share':round(s/total*100,1)} for st,s in salt_sales.items()]
brand_sales = plot.groupby('brand')['revenue'].sum().sort_values(ascending=False)
all_brands = [{'brand':b,'sales':int(s),'share':round(s/total*100,1)} for b,s in brand_sales.items()]
shop_sales = plot.groupby('shop')['revenue'].sum().sort_values(ascending=False)
all_shops = [{'shop':sh,'sales':int(s),'share':round(s/total*100,1)} for sh,s in shop_sales.items()]
w_sales = plot.groupby('weight_key')['revenue'].sum().sort_values(ascending=False)
all_weights = [{'weight':w,'sales':int(s),'share':round(s/total*100,1)} for w,s in w_sales.items()]

data = []
for _, row in plot.iterrows():
    data.append({
        'brand': str(row['brand']),
        'salt': str(row['salt_type']),
        'shop': str(row['shop']),
        'weight': str(row['weight_key']),
        'sales': int(row['sales']),
        'unit': float(round(row['unit_price'],2)),
        'order': float(round(row['order_price'],2)),
        'pid': str(int(row['product_id'])) if pd.notna(row['product_id']) else '',
        'sku': str(row['sku_info']),
        'revenue': float(round(row['revenue'],2)),
        'rank': int(row['rank'])
    })

salt_types = sorted(plot['salt_type'].unique().tolist())

with open(js_path, 'w', encoding='utf-8') as f:
    f.write("var BUBBLE_DATA = ")
    json.dump({
        'data': data, 'salt_types': salt_types, 'salt_shares': salt_shares,
        'all_brands': all_brands, 'all_shops': all_shops,
        'all_weights': all_weights, 'total_sales': total
    }, f, ensure_ascii=False)
    f.write(";")
print(f'Done. {len(data)} records, {plot.brand.nunique()} brands.')
