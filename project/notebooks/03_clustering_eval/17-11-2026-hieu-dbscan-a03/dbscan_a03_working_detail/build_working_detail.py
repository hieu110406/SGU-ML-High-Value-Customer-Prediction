from pathlib import Path
import hashlib
import json
import math
import textwrap
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.workbook.properties import CalcProperties
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(__file__).resolve().parent
MODEL = ROOT / 'project/notebooks/03_clustering_eval/17-11-2026-hieu-dbscan-a03'
DATA = ROOT / 'project/notebooks/02_baseline_kmeans/12-11-2026-hieu-kmeans/data/customer_features.csv'
SOURCE = Path('D:/down/nhatky_capnhat.xlsx')
OUT = DEST / 'Working_details_DBSCAN_A03.xlsx'
FEATURES = ['Recency', 'Frequency', 'Monetary']
NAVY, BLUE, PALE, GRAY, INK = '26476B', 'DDEAF5', 'F4F7FA', '63758A', '172B40'
FORMULAS = {}

# Read existing artifacts only. No fitting or changes to preprocessing.
df = pd.read_csv(DATA, dtype={'CustomerID': 'string'})
assignments = pd.read_csv(MODEL / 'data/dbscan_a03_labels.csv', dtype={'CustomerID': 'string'})
grid = pd.read_csv(MODEL / 'data/dbscan_a03_grid.csv')
params = json.loads((MODEL / 'data/dbscan_a03_params.json').read_text(encoding='utf-8'))
assert df.CustomerID.is_unique and assignments.CustomerID.is_unique
assert set(df.CustomerID) == set(assignments.CustomerID)
joined = df[['CustomerID'] + FEATURES].merge(assignments, on='CustomerID', validate='one_to_one')
assert joined[FEATURES + ['cluster']].notna().all().all()
valid = grid[(grid.n_clusters >= 2) & (grid.noise_pct <= 5) & grid.silhouette.notna()]
assert len(valid) > 0
selected = valid.sort_values('silhouette', ascending=False).iloc[0]
assert selected.eps == params['eps'] and selected.min_samples == params['min_samples']
for key, artifact_key in [('silhouette', 'silhouette_non_noise'), ('dbi', 'dbi_non_noise'),
                          ('noise_pct', 'noise_pct'), ('n_clusters', 'n_clusters')]:
    assert math.isclose(float(selected[key]), params[artifact_key], rel_tol=1e-10)
counts = joined.groupby('cluster').size()
assert math.isclose(counts.get(-1, 0) / len(joined) * 100, params['noise_pct'])
assert len(counts.drop(-1, errors='ignore')) == params['n_clusters']
prof = joined.groupby('cluster').agg(customers=('Monetary', 'size'), Recency=('Recency', 'median'),
    Frequency=('Frequency', 'median'), Monetary=('Monetary', 'median'), Monetary_sum=('Monetary', 'sum'))
total_m = float(prof.Monetary_sum.sum())
assert math.isclose(total_m, float(joined.Monetary.sum()), rel_tol=1e-12)


def preview(ws, cell_range, filename):
    # Fallback visual QA from the saved Excel cell geometry and styles.
    from openpyxl.utils.cell import range_boundaries
    c1, r1, c2, r2 = range_boundaries(cell_range)
    widths = {c: int(ws.column_dimensions[ws.cell(1, c).column_letter].width * 7 + 5) for c in range(c1, c2+1)}
    heights = {r: int((ws.row_dimensions[r].height or 18) * 1.34) for r in range(r1, r2+1)}
    xs, ys = {c1: 0}, {r1: 0}
    for c in range(c1, c2+1): xs[c+1] = xs[c] + widths[c]
    for r in range(r1, r2+1): ys[r+1] = ys[r] + heights[r]
    im = Image.new('RGB', (xs[c2+1]+1, ys[r2+1]+1), 'white')
    draw = ImageDraw.Draw(im)
    merges = list(ws.merged_cells.ranges)
    for r in range(r1, r2+1):
        for c in range(c1, c2+1):
            cell = ws.cell(r, c)
            merge = next((m for m in merges if m.min_row <= r <= m.max_row and m.min_col <= c <= m.max_col), None)
            if merge and (r != merge.min_row or c != merge.min_col): continue
            endc = min(merge.max_col, c2) if merge else c
            endr = min(merge.max_row, r2) if merge else r
            box = [xs[c], ys[r], xs[endc+1], ys[endr+1]]
            if cell.fill.fgColor.type == 'rgb' and cell.fill.patternType == 'solid':
                draw.rectangle(box, fill='#' + cell.fill.fgColor.rgb[-6:])
            value = cell.value
            if value is None: continue
            value = FORMULAS.get((ws.title, cell.coordinate), (None, value))[1]
            if isinstance(value, datetime): value = value.strftime('%d/%m/%Y')
            elif isinstance(value, (int, float)):
                fmt = cell.number_format
                if '%' in fmt: value = f'{value:.2%}'
                elif '0.0000' in fmt: value = f'{value:.4f}'
                elif '0.00' in fmt: value = f'{value:,.2f}'
                else: value = f'{value:,.0f}'
            else: value = str(value)
            size = round((cell.font.sz or 11) * 1.34)
            font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if cell.font.b else 'C:/Windows/Fonts/arial.ttf', size)
            maxwidth = box[2] - box[0] - 12
            lines = []
            for paragraph in value.split('\n'):
                if cell.alignment.wrap_text:
                    line = ''
                    for word in paragraph.split():
                        candidate = (line + ' ' + word).strip()
                        if draw.textlength(candidate, font=font) > maxwidth and line:
                            lines.append(line); line = word
                        else: line = candidate
                    lines.append(line)
                else: lines.append(paragraph)
            lh = size + 4
            if len(lines)*lh > box[3]-box[1]-5:
                raise AssertionError(f'Clipped vertical text: {ws.title}!{cell.coordinate} {lines}')
            color = '#' + cell.font.color.rgb[-6:] if cell.font.color and cell.font.color.type == 'rgb' else '#172B40'
            y = box[1] + max(4, (box[3]-box[1]-len(lines)*lh)/2)
            for line in lines:
                tw = draw.textlength(line,font=font)
                if tw > maxwidth + 1: raise AssertionError(f'Clipped width: {ws.title}!{cell.coordinate}: {line}')
                align = cell.alignment.horizontal
                x = box[2]-tw-6 if align == 'right' or isinstance(cell.value, (int,float)) else box[0]+6
                if align == 'center': x = box[0] + (box[2]-box[0]-tw)/2
                draw.text((x,y),line,font=font,fill=color); y += lh
    im.save(DEST / filename)


# Reference is inspected without applying any instructions in its cells.
reference = load_workbook(SOURCE, data_only=True)
# Record source layout for comparison, without modifying the reference workbook.
(DEST / 'reference_layout.json').write_text(json.dumps({s.title: {'rows':s.max_row,'columns':s.max_column,
    'merges':[str(m) for m in s.merged_cells.ranges]} for s in reference},ensure_ascii=False,indent=2),encoding='utf-8')

wb = Workbook()
wb.remove(wb.active)
for name in ['ketqua', 'tinhchinh', 'hosocum', 'nhatky']:
    wb.create_sheet(name)
wb.calculation = CalcProperties(calcId=191029, fullCalcOnLoad=True, forceFullCalc=True)


def setup(name, widths, endrow):
    ws = wb[name]
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(1,i).column_letter].width = width
    for row in ws.iter_rows(min_row=1,max_row=endrow,max_col=len(widths)):
        for c in row:
            c.font = Font(name='Arial',size=11,color=INK)
            c.alignment = Alignment(vertical='center',wrap_text=True)
        ws.row_dimensions[row[0].row].height = 26
    ws.row_dimensions[1].height = 9
    ws.print_options.horizontalCentered = True
    ws.print_area = f'A1:{ws.cell(endrow,len(widths)).coordinate}'
    return ws


def value(ws, address, data, fmt=None):
    ws[address] = data
    if fmt: ws[address].number_format = fmt
    if isinstance(data,(int,float)):
        ws[address].alignment = Alignment(horizontal='right',vertical='center',wrap_text=True)


def formula(ws,address,expr,cached,fmt=None):
    value(ws,address,expr,fmt)
    FORMULAS[(ws.title,address)] = (expr,cached)
    ws[address].alignment = Alignment(horizontal='right' if isinstance(cached,(int,float)) else 'left',vertical='center',wrap_text=True)


def band(ws, row, last, text):
    ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=last)
    value(ws,f'A{row}',text)
    for cells in ws.iter_rows(min_row=row,max_row=row,max_col=last):
        for c in cells:
            c.fill = PatternFill('solid',fgColor=BLUE)
            c.font = Font(name='Arial',size=11,bold=True,color=NAVY)


def title(ws, last, text):
    ws.merge_cells(start_row=2,start_column=1,end_row=2,end_column=last)
    value(ws,'A2',text)
    ws['A2'].font = Font(name='Arial',size=16,bold=True,color=NAVY)
    ws.row_dimensions[2].height = 34
    for c in ws[2][:last]: c.border = Border(bottom=Side(style='thin',color=NAVY))


def header(ws,row,headers):
    for col,txt in enumerate(headers,1):
        c=ws.cell(row,col,txt)
        c.fill=PatternFill('solid',fgColor=NAVY)
        c.font=Font(name='Arial',size=11,bold=True,color='FFFFFF')
        c.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
    ws.row_dimensions[row].height=44


def textrow(ws,row,last,txt,height=42):
    ws.merge_cells(start_row=row,start_column=1,end_row=row,end_column=last)
    value(ws,f'A{row}',txt)
    ws.row_dimensions[row].height=height


ws=setup('ketqua',[29,44,3,30,23,41],34)
ws.sheet_properties.tabColor=NAVY
title(ws,6,'WORKING DETAIL DBSCAN A03')
textrow(ws,3,6,'Người thực hiện: Hiếu. Ngày lập Working Detail: 18/11/2026. Phạm vi: một model DBSCAN A03.',28)
for r in [5]:
    for a,b,txt in [('A','B','Thiết lập'),('D','F','Kết quả cấu hình được chọn')]:
        ws.merge_cells(f'{a}{r}:{b}{r}'); ws[f'{a}{r}']=txt
        for row in ws[f'{a}{r}:{b}{r}']:
            for c in row:c.fill=PatternFill('solid',fgColor=BLUE); c.font=Font(name='Arial',bold=True,size=11,color=NAVY)
settings=[('Mô hình','DBSCAN'),('Mã thử nghiệm','A03-DB'),('Đặc trưng','Recency, Frequency, Monetary'),
    ('Chuẩn hóa','StandardScaler; không log1p'),('PCA','Cố định 2 thành phần'),
    ('Phương sai giữ lại',params['pca_explained_variance_ratio']),('Khoảng cách','Euclid'),
    ('Khách đầu vào',len(joined)),('Nhiễu tối đa',0.05),('Số cụm tối thiểu',2),
    ('Quy tắc chọn','Silhouette cao nhất trong cấu hình đạt điều kiện')]
for row,(a,b) in enumerate(settings,6):
    value(ws,f'A{row}',a); value(ws,f'B{row}',b)
    if row in [8,9,10,16]:ws.row_dimensions[row].height=42
ws['B11'].number_format=ws['B14'].number_format='0.00%'
ws['B13'].number_format='#,##0'
grid_excel_row=int(grid.index[(grid.eps==params['eps']) & (grid.min_samples==params['min_samples'])][0])+6
stats=[('eps',f"='tinhchinh'!B{grid_excel_row}",params['eps'],'0.00','Bán kính lân cận trong không gian PCA'),
    ('min_samples',f"='tinhchinh'!A{grid_excel_row}",params['min_samples'],'0','Tính cả chính điểm đang xét'),
    ('Silhouette',f"='tinhchinh'!G{grid_excel_row}",params['silhouette_non_noise'],'0.0000','Càng cao càng tốt; loại nhiễu'),
    ('Davies–Bouldin',f"='tinhchinh'!H{grid_excel_row}",params['dbi_non_noise'],'0.0000','Càng thấp càng tốt; loại nhiễu'),
    ('Số cụm',f"='tinhchinh'!C{grid_excel_row}",params['n_clusters'],'0','Không tính nhãn -1'),
    ('Tỷ lệ nhiễu',f"='tinhchinh'!D{grid_excel_row}",params['noise_pct']/100,'0.00%','Tính trên toàn bộ khách đầu vào'),
    ('Cụm lớn nhất',f"='tinhchinh'!E{grid_excel_row}",float(selected.largest_pct)/100,'0.00%','Tính trên toàn bộ khách đầu vào'),
    ('Cụm nhỏ nhất',f"='tinhchinh'!F{grid_excel_row}",int(selected.smallest),'#,##0','Số khách, không tính nhiễu'),
    ('Số cấu hình khảo sát',"=COUNTA('tinhchinh'!A6:A59)",len(grid),'0','Toàn bộ lưới eps × min_samples'),
    ('Số cấu hình đạt',"=COUNTIF('tinhchinh'!I6:I59,\"Đạt\")",len(valid),'0','Đủ số cụm, nhiễu và có Silhouette')]
for row,(label,expr,cached,fmt,note) in enumerate(stats,6):
    value(ws,f'D{row}',label);formula(ws,f'E{row}',expr,cached,fmt);value(ws,f'F{row}',note)
band(ws,18,6,'Nhận xét cho riêng DBSCAN A03')
textrow(ws,19,6,f"Cấu hình được chọn: eps={params['eps']}, min_samples={params['min_samples']}; Silhouette={params['silhouette_non_noise']:.4f}, DBI={params['dbi_non_noise']:.4f}. Các điểm nhiễu không tham gia hai chỉ số này.",40)
textrow(ws,20,6,f"Cụm lớn nhất chiếm {selected.largest_pct:.2f}% số khách. Kết quả thiên về tách một nhóm nhỏ khỏi khối chính; điểm số cao chưa đủ để kết luận phân khúc cân đối hoặc hữu ích.",40)
textrow(ws,21,6,'Nhãn -1 là nhiễu theo mật độ, không đồng nghĩa khách kém giá trị. Xem đồng thời hồ sơ RFM và tỷ trọng Monetary trước khi đặt tên nghiệp vụ.',40)
textrow(ws,22,6,'Đánh giá nội bộ trên cùng tập khách; chưa có đánh giá độc lập. Working Detail này chỉ ghi kết quả A03, không kết luận tương đương A01 hoặc so sánh các model.',40)
band(ws,24,6,'Nguồn dữ liệu và bằng chứng')
textrow(ws,25,6,'Đầu vào: notebooks/02_baseline_kmeans/12-11-2026-hieu-kmeans/data/customer_features.csv (file đã tiền xử lý của nhóm).',40)
textrow(ws,26,6,'SHA-256 đầu vào: '+hashlib.sha256(DATA.read_bytes()).hexdigest(),30)
textrow(ws,27,6,'Kết quả: dbscan_a03_grid.csv, dbscan_a03_labels.csv và dbscan_a03_params.json trong thư mục data của model A03.',34)
textrow(ws,28,6,'Notebook minh chứng: notebooks/03_clustering_eval/17-11-2026-hieu-dbscan-a03/dbscan.ipynb. Hồ sơ cụm được tính lại từ nhãn đã lưu, ghép theo CustomerID.',40)
textrow(ws,29,6,'Chỉ ghi nhận kết quả trên đầu vào đã tiền xử lý; chưa xác minh chuỗi xử lý từ raw đến file feature. Không dùng workbook này làm bằng chứng kiểm chứng raw.',40)
textrow(ws,30,6,'Phương pháp: đọc artifact hiện có và đối chiếu tính nhất quán; không huấn luyện lại, không thay đổi dữ liệu tiền xử lý.',30)

ws=setup('tinhchinh',[15,13,14,17,20,19,17,17,15,18],66)
title(ws,10,'THỬ THAM SỐ DBSCAN A03')
textrow(ws,3,10,'eps: 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0. min_samples: 4, 6, 8, 10, 15, 20.',28)
textrow(ws,4,10,'Chọn Silhouette lớn nhất khi có ít nhất 2 cụm và nhiễu ≤ 5%. Silhouette và DBI tính trên PCA 2D, chỉ với điểm không nhiễu.',30)
header(ws,5,['min_samples','eps','Số cụm','Nhiễu (%)','Cụm lớn nhất (%)','Cụm nhỏ nhất (khách)','Silhouette','DBI','Điều kiện','Cấu hình chọn'])
for row,(_,g) in enumerate(grid.iterrows(),6):
    values=[int(g.min_samples),float(g.eps),int(g.n_clusters),float(g.noise_pct)/100,
        None if pd.isna(g.largest_pct) else float(g.largest_pct)/100,int(g.smallest),
        None if pd.isna(g.silhouette) else float(g.silhouette),None if pd.isna(g.dbi) else float(g.dbi)]
    for col,v in enumerate(values,1):value(ws,ws.cell(row,col).coordinate,v)
    achieved=bool(g.n_clusters>=2 and g.noise_pct<=5 and pd.notna(g.silhouette))
    formula(ws,f'I{row}',f'=IF(AND(C{row}>=ketqua!$B$15,D{row}<=ketqua!$B$14,ISNUMBER(G{row})),"Đạt","Không đạt")','Đạt' if achieved else 'Không đạt')
    value(ws,f'J{row}','Được chọn' if row==grid_excel_row else None)
    for col in ['D','E']:ws[f'{col}{row}'].number_format='0.00%'
    for col in ['G','H']:ws[f'{col}{row}'].number_format='0.0000'
    ws[f'B{row}'].number_format='0.00'
    if row==grid_excel_row:
        for c in ws[row][:10]:c.fill=PatternFill('solid',fgColor='DCECDF');c.font=Font(name='Arial',size=11,bold=True,color=INK)
tab=Table(displayName='DBSCAN_A03_Grid',ref=f'A5:J{5+len(grid)}')
tab.tableStyleInfo=TableStyleInfo(name='TableStyleLight9',showRowStripes=True)
ws.add_table(tab)
ws.freeze_panes='C6';ws.print_title_rows='1:5'
textrow(ws,61,10,'Ô trống ở Silhouette/DBI: không có đủ số cụm hợp lệ để tính; không phải điểm số 0.',30)
textrow(ws,62,10,'Bảng ghi toàn bộ cấu hình đã chạy. Cấu hình được chọn và nhãn là ảnh chụp kết quả artifact, không tự huấn luyện lại khi sửa ô Excel.',36)
textrow(ws,63,10,'Nguồn: data/dbscan_a03_grid.csv và data/dbscan_a03_params.json của model A03.',30)

ws=setup('hosocum',[11,22,17,19,19,19,23,25,23],20)
title(ws,9,'HỒ SƠ CỤM DBSCAN A03')
textrow(ws,3,9,'RFM trên thang gốc trước StandardScaler/PCA. Monetary là chi tiêu mua lịch sử (GBP), chưa phản ánh lợi nhuận hoặc giá trị tương lai.',34)
textrow(ws,4,9,'Tỷ trọng khách và Monetary đều dùng toàn bộ đầu vào làm mẫu số, gồm cả nhiễu -1.',28)
header(ws,5,['Nhãn','Nhóm','Số khách','Tỷ lệ khách (%)','Recency median (ngày)','Frequency median (hóa đơn)','Monetary median (GBP)','Tổng Monetary (GBP)','Tỷ trọng Monetary (%)'])
last=5+len(prof)
for row,(cl,p) in enumerate(prof.iterrows(),6):
    group='Nhiễu' if cl==-1 else 'Cụm chính' if p.customers==prof.drop(-1,errors='ignore').customers.max() else 'Cụm nhỏ'
    for col,v in enumerate([int(cl),group,int(p.customers),None,float(p.Recency),float(p.Frequency),float(p.Monetary),float(p.Monetary_sum)],1):
        value(ws,ws.cell(row,col).coordinate,v)
    formula(ws,f'D{row}',f'=C{row}/SUM($C$6:$C${last})',int(p.customers)/len(joined),'0.00%')
    formula(ws,f'I{row}',f'=H{row}/SUM($H$6:$H${last})',float(p.Monetary_sum)/total_m,'0.00%')
    for col in ['E','F','G','H']:ws[f'{col}{row}'].number_format='#,##0.00'
    if cl==-1:
        for c in ws[row][:9]:c.fill=PatternFill('solid',fgColor='FFF0D6')
totalrow=last+1
value(ws,f'B{totalrow}','Tổng')
for col,cache,fmt in [('C',len(joined),'#,##0'),('D',1.,'0.00%'),('H',total_m,'#,##0.00'),('I',1.,'0.00%')]:
    formula(ws,f'{col}{totalrow}',f'=SUM({col}6:{col}{last})',cache,fmt)
for c in ws[totalrow][:9]:c.font=Font(name='Arial',size=11,bold=True,color=NAVY);c.border=Border(top=Side(style='thin',color=NAVY))
band(ws,12,9,'Diễn giải')
for row,(cl,p) in enumerate(prof.iterrows(),13):
    textrow(ws,row,9,f"Nhóm {'nhiễu (-1)' if cl==-1 else int(cl)}: {int(p.customers):,} khách; R median={p.Recency:.2f} ngày, F median={p.Frequency:.2f} hóa đơn, M median={p.Monetary:,.2f} GBP; đóng góp {p.Monetary_sum/total_m:.2%} tổng Monetary.",36)
textrow(ws,17,9,'Nguồn: customer_features.csv ghép data/dbscan_a03_labels.csv theo CustomerID (một dòng mỗi khách). Trung vị không cộng gộp giữa các cụm.',34)
textrow(ws,18,9,'Nhãn cụm chỉ là mã định danh. Tên nhóm mô tả quy mô, chưa tự gán VIP hoặc xếp hạng giá trị.',28)

ws=setup('nhatky',[17,14,38,44,61,51],14)
title(ws,6,'NHẬT KÝ RIÊNG DBSCAN A03')
textrow(ws,3,6,'Các bước model được đối chiếu từ notebook và artifact; chưa có ngày thực hiện từng bước. Ngày 18/11/2026 là ngày lập Working Detail.',34)
header(ws,5,['Ngày thực hiện','Người thực hiện','Công việc','Tham số / cách làm','Kết quả ghi nhận','Minh chứng'])
records=[
    (None,'Hiếu','Sử dụng tập RFM đã tiền xử lý','Recency, Frequency, Monetary; một dòng mỗi CustomerID',f'{len(joined):,} khách; giữ nguyên file feature.','customer_features.csv; ô đọc dữ liệu trong dbscan.ipynb'),
    (None,'Hiếu','Chuẩn hóa và PCA','StandardScaler; PCA cố định 2 thành phần',f"Giữ {params['pca_explained_variance_ratio']:.2%} phương sai; không phải PCA ngưỡng 95%.",'dbscan.ipynb; dbscan_a03_params.json'),
    (None,'Hiếu','Khảo sát eps × min_samples','9 mức eps × 6 mức min_samples',f'{len(grid)} cấu hình; {len(valid)} cấu hình đạt số cụm và nhiễu.','data/dbscan_a03_grid.csv; figures/A03_k_distance.png'),
    (None,'Hiếu','Chọn cấu hình','≥ 2 cụm; nhiễu ≤ 5%; Silhouette cao nhất',f"eps={params['eps']}; min_samples={params['min_samples']}; Silhouette={params['silhouette_non_noise']:.4f}; DBI={params['dbi_non_noise']:.4f}.",'data/dbscan_a03_params.json'),
    (None,'Hiếu','Mô tả cụm và nhiễu','Trung vị RFM; tỷ trọng khách và Monetary',f"{params['n_clusters']} cụm; {int(counts.get(-1,0))} khách nhiễu. Cụm lớn nhất chiếm {selected.largest_pct:.2f}% khách.",'data/dbscan_a03_labels.csv; sheet hosocum'),
    (datetime(2026,11,18),'Hiếu','Lập Working Detail cho A03','Tổng hợp artifact hiện có; đối chiếu khóa CustomerID','Ghi thiết lập, toàn bộ lưới tham số, kết quả chọn và hồ sơ cụm của riêng model A03.','Working_details_DBSCAN_A03.xlsx'),
]
for row,record in enumerate(records,6):
    ws.row_dimensions[row].height=76
    for col,v in enumerate(record,1):value(ws,ws.cell(row,col).coordinate,v)
    if record[0] is None:
        ws[f'A{row}'].fill=PatternFill('solid',fgColor='FFF0D6')
    else:ws[f'A{row}'].number_format='dd/mm/yyyy'
    if row%2==0:
        for c in ws[row][1:]:c.fill=PatternFill('solid',fgColor=PALE)
textrow(ws,13,6,'Ô ngày để trống: chưa ghi nhận ngày thực hiện. Có thể bổ sung ngày thật khi tổng hợp nhật ký nhóm.',30)
ws.freeze_panes='C6'

wb.save(OUT)

# Cache independently computed formula results. Excel recalculates them on open.
# No native Excel engine is available in this environment.
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
with zipfile.ZipFile(OUT,'r') as z:
    content={n:z.read(n) for n in z.namelist()}
for idx,ws in enumerate(wb,1):
    name=f'xl/worksheets/sheet{idx}.xml'
    tree=ET.fromstring(content[name])
    for c in tree.findall(f'.//{{{NS}}}c'):
        entry=FORMULAS.get((ws.title,c.attrib['r']))
        if not entry:continue
        cache=entry[1]
        v=c.find(f'{{{NS}}}v')
        if v is None:v=ET.SubElement(c,f'{{{NS}}}v')
        if isinstance(cache,str):c.set('t','str');v.text=cache
        else:c.attrib.pop('t',None);v.text=str(cache)
    content[name]=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
    for n,data in content.items():z.writestr(n,data)

saved=load_workbook(OUT,data_only=True)
assert saved['ketqua']['E6'].value==params['eps']
assert saved['ketqua']['E8'].value==params['silhouette_non_noise']
assert saved['hosocum'][f'C{totalrow}'].value==len(joined)
for ws in saved:
    for row in ws:
        for c in row:
            assert c.data_type!='e',f'Excel error {ws.title}!{c.coordinate}'
for name,rng in [('ketqua','A1:F30'),('tinhchinh','A1:J18'),('hosocum','A1:I18'),('nhatky','A1:F13')]:
    preview(saved[name],rng,f'{name}_preview.png')
report={'output':str(OUT),'sheets':saved.sheetnames,'customers':len(joined),'grid_rows':len(grid),
    'eligible':len(valid),'checked_formulas':len(FORMULAS),'native_recalculation':False,
    'source_features_sha256':hashlib.sha256(DATA.read_bytes()).hexdigest()}
(DEST/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
