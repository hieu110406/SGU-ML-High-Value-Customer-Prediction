"""Compare exported EDA with a separately computed raw-workbook profile."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import runpy
import numpy as np
import pandas as pd

ROOT=next(parent for parent in Path(__file__).resolve().parents
          if (parent/'project/data/raw/Online Retail.xlsx').is_file())
OUT=ROOT/'project/experiments/eda_raw_moi'
WORKBOOK=OUT/'ket_qua_eda.xlsx'
profile=runpy.run_path(str(OUT/'verification/independent_profile.py'))['result']
excel=pd.ExcelFile(WORKBOOK,engine='openpyxl')
catalog=pd.read_excel(excel,sheet_name='Danh_muc_bang').set_index('table_id')
checks=[]

def compare(name,actual,expected,rtol=1e-10,atol=1e-9):
    try:
        equal=bool(np.isclose(float(actual),float(expected),rtol=rtol,atol=atol))
    except (ValueError,TypeError):
        equal=str(actual)==str(expected)
    if isinstance(actual,np.generic): actual=actual.item()
    if isinstance(expected,np.generic): expected=expected.item()
    checks.append(dict(check=name,actual=actual,expected=expected,passed=equal))

def read(name,index=None):
    return pd.read_excel(excel,sheet_name=catalog.loc[name,'sheet'],index_col=index)

inv=read('raw_inventory').set_index('item').value
r=profile['raw']; p=profile['purchase']
for name,key in [('rows','rows'),('columns','columns'),('invoices_including_C','invoices'),('known_customer_ids','customers'),('stock_codes','stockcodes'),('countries','countries'),('date_min','date_min'),('date_max','date_max')]:
    compare(f'raw_inventory.{name}',inv[name],r[key])
compare('raw_sha256.inventory',inv['sha256'],profile['sha256'])
compare('raw_sha256.after',hashlib.sha256((ROOT/profile['path']).read_bytes()).hexdigest(),profile['sha256'])
for sheet in read('workbook_sheets').to_dict('records'):
    expected=profile['sheets'][sheet['sheet']]
    for name,key in [('rows','rows'),('columns','columns'),('all_blank_rows','all_null_rows'),('repeated_header_rows','repeated_header_rows')]:
        compare(f'sheet.{sheet["sheet"]}.{name}',sheet[name],expected[key])

missing=read('missing_values').set_index('column')
for col,count in r['missing'].items(): compare(f'missing.{col}',missing.loc[col,'raw_null_count'],count)
quality=read('quality_issues').set_index('issue')
for name,key in [('missing_customer','missing_customer'),('missing_description','missing_description'),('exact_duplicate_extra','duplicate_excess'),('C_prefix','c_prefix'),('quantity_negative','negative_quantity'),('quantity_zero','zero_quantity'),('price_negative','negative_price'),('price_zero','zero_price')]:
    for main,ind in [('rows','rows'),('invoices','invoices'),('known_customers','customers'),('signed_value','signed_value')]:
        compare(f'quality.{name}.{main}',quality.loc[name,main],r['cohorts'][key][ind])
    if 'absolute_value' in quality.columns:
        compare(f'quality.{name}.absolute_value',quality.loc[name,'absolute_value'],r['cohorts'][key]['absolute_value'])
compare('quality.duplicate_all_members',quality.loc['all_rows_in_duplicate_groups','rows'],r['duplicate_all_members'])
if 'rows_zero_price' in quality.columns:
    compare('quality.missing_description.zero_price',quality.loc['missing_description','rows_zero_price'],r['cohorts']['missing_description']['rows'])
if 'rows_missing_customer' in quality.columns:
    compare('quality.missing_description.missing_customer',quality.loc['missing_description','rows_missing_customer'],r['cohorts']['missing_description']['rows'])

coverage=read('customer_coverage').set_index('metric').value
for name,key in [('temporary_purchase_customers','customers'),('customers_one_invoice','single_invoice_customers'),('pct_customers_one_invoice','single_invoice_customer_pct'),('temporary_purchase_value','signed_value')]:
    compare(f'coverage.{name}',coverage[name],p[key])
compare('coverage.raw_signed_value',coverage.raw_signed_value,r['signed_value'])
compare('coverage.signed_missing_id',coverage.signed_value_missing_id,r['cohorts']['missing_customer']['signed_value'])
compare('coverage.gap_defined',coverage.gap_defined_customers,p['customers']-p['mean_gap_missing'])
scopes=read('analysis_scopes').set_index('scope')
for main,ind in [('observations','rows'),('invoices','invoices'),('customers','customers')]:
    compare(f'purchase.{main}',scopes.loc['temporary_purchase',main],p[ind])

raw_map={'Quantity':'Quantity','UnitPrice':'UnitPrice','SignedLineValue':'LineValue'}
cust_map={'n_invoices':'Frequency','monetary':'Monetary','avg_order_value':'AOV','n_stock_codes':'DistinctProducts','recency_days':'Recency','observed_span_days':'ActiveSpanDays','avg_purchase_gap_days':'MeanGapDays'}
stat_map={'count':'count','minimum':'min','maximum':'max','mean':'mean','median':'50%','std':'std','q1':'25%','q3':'75%','p95':'95%','p99':'99%'}
for table,mapping,expected in [('numeric_summary',raw_map,r['numeric']),('customer_summary',cust_map,p['describe'])]:
    data=read(table).set_index('variable')
    for variable,key in mapping.items():
        for stat,indstat in stat_map.items(): compare(f'{table}.{variable}.{stat}',data.loc[variable,stat],expected[key][indstat])

for level,mapping,expected in [('line',raw_map,r),('customer',cust_map,p)]:
    for method in ['pearson','spearman']:
        data=read(f'correlations_{level}_{method}',0)
        for a,ia in mapping.items():
            for b,ib in mapping.items():
                compare(f'correlation.{level}.{method}.{a}.{b}',data.loc[a,b],expected[method][ia][ib])
    pairs=read(f'correlations_{level}_pairwise_counts',0)
    for a,ia in mapping.items():
        for b,ib in mapping.items():
            compare(f'paircount.{level}.{a}.{b}',pairs.loc[a,b],r['rows'] if level=='line' else p['pair_counts'][ia][ib])
    compare(f'identifiers_excluded.{level}',bool(not {'InvoiceNo','CustomerID','StockCode'}.intersection(data.columns)),True)

monthly=read('monthly_activity').set_index('month')
for row in r['monthly']:
    for main,ind in [('rows','Rows'),('invoices','Invoices'),('signed_line_value','SignedValue')]:
        compare(f'monthly.{row["Month"]}.{main}',monthly.loc[row['Month'],main],row[ind])

conf=read('identifier_conflicts').set_index(['key','attribute'])
for key,col,ind in [('InvoiceNo','CustomerID','invoice_multi_customer'),('InvoiceNo','Country','invoice_multi_country'),('CustomerID','Country','customer_multi_country'),('StockCode','Description','stock_multi_description'),('Description','StockCode','description_multi_stock')]:
    compare(f'conflicts.{key}.{col}',conf.loc[(key,col),'keys_multiple_values'],r[ind]['count'])

metadata={row.item:json.loads(row.value_json) for row in pd.read_excel(excel,sheet_name='Metadata').itertuples()}
compare('metadata.raw_sha256',metadata['raw_sha256'],profile['sha256'])
compare('metadata.legacy_unchanged',metadata['protected_before']==metadata['protected_after'],True)
for name,sha in metadata['code_sha256'].items():
    path=ROOT/'project/notebooks/01_eda'/name
    compare(f'metadata.code_sha256.{name}',hashlib.sha256(path.read_bytes()).hexdigest(),sha)

desc_counts={
    'exact_raw_stock_multiple_descriptions':r['stock_multi_description']['count'],
    'exported_stock_multiple_descriptions':int(conf.loc[('StockCode','Description'),'keys_multiple_values']),
    'exact_raw_description_multiple_stock':r['description_multi_stock']['count'],
    'exported_description_multiple_stock':int(conf.loc[('Description','StockCode'),'keys_multiple_values']),
}
result=dict(
    verified_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
    independent_input_sha256=profile['sha256'],
    independent_profile_script='project/experiments/eda_raw_moi/verification/independent_profile.py',
    independent_profile='Calculated directly from raw in memory',
    comparison_script='project/experiments/eda_raw_moi/verification/validate_independent.py',
    comparison_scope='Independent direct workbook calculation vs exported new EDA; no old results used',
    passed=sum(x['passed'] for x in checks),failed=sum(not x['passed'] for x in checks),
    description_mapping_scope=desc_counts,
    description_mapping_note=('Exported Description is whitespace-stripped. Exact raw description counts '
        'must not cite these normalized counts without disclosing the scope difference.'
        if desc_counts['exact_raw_stock_multiple_descriptions']!=desc_counts['exported_stock_multiple_descriptions']
        or desc_counts['exact_raw_description_multiple_stock']!=desc_counts['exported_description_multiple_stock']
        else 'Exact raw and exported description mapping counts agree.'),
    limitations=['Numerical checks only. No visual inspection by this reviewer.',
                 'Independent profile has 7 customer variables; extra active_days/total_quantity checked by main pipeline, not independently here.'],
    checks=checks)
excel.close()
with pd.ExcelWriter(WORKBOOK,engine='openpyxl',mode='a',if_sheet_exists='replace') as writer:
    pd.DataFrame(checks).to_excel(writer,sheet_name='Kiem_chung_doc_lap',index=False)
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
if result['failed']:
    print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False,indent=2))
    raise SystemExit(1)
