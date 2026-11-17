import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load('D:/down/nhatky_capnhat.xlsx'));
console.log((await wb.inspect({kind:'region',sheetId:'nhatky',range:'C1:P8',maxChars:2400,tableMaxRows:3})).ndjson);
const preview = await wb.render({sheetName:'nhatky',range:'C1:P8',scale:1,format:'png'});
await fs.writeFile('outputs/dbscan_a03_working_detail/reference.png',new Uint8Array(await preview.arrayBuffer()));
