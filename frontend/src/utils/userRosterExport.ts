import { CustomField, UserType } from '../types/onboarding';

export interface EncryptedFieldValue {
  ciphertext: string;
  ephemeral_pubkey: string;
}

export interface UserRosterExportUser {
  id: number;
  pubkey?: string | null;
  email?: string | null;
  name?: string | null;
  email_encrypted?: EncryptedFieldValue | null;
  name_encrypted?: EncryptedFieldValue | null;
  user_type_id: number | null;
  user_type?: UserType | null;
  approved: boolean;
  created_at?: string | null;
  fields?: Record<string, unknown>;
  fields_encrypted?: Record<string, EncryptedFieldValue | null | undefined>;
}

export interface UserRosterIdentity {
  status: 'decrypting' | 'ready' | 'unavailable' | 'failed';
  email: string | null;
  name: string | null;
}

export interface UserRosterWorkbookInput {
  users: UserRosterExportUser[];
  userTypes: UserType[];
  onboardingFields: CustomField[];
  identities: Record<number, UserRosterIdentity | undefined>;
  profileValues: Record<number, Record<string, string | null | undefined>>;
  exportedAt: Date;
  exportedBy?: string | null;
}

export interface UserRosterWorkbook {
  blob: Blob;
  filename: string;
  includesDecryptedValues: boolean;
}

interface DateCell {
  kind: 'date';
  value: string | Date | null | undefined;
}

type CellValue = string | number | boolean | DateCell | null | undefined;
type SheetRows = CellValue[][];

interface SheetDefinition {
  name: string;
  rows: SheetRows;
}

const LOCKED_VALUE = 'Locked';
const MISSING_VALUE = '';
const COPIED_EXPORT_NOTICE =
  'Downloaded User Roster Export spreadsheets are Copied Exports. They leave active product storage and become operator/device controlled records after creation.';

function isDateCell(value: CellValue): value is DateCell {
  return Boolean(value && typeof value === 'object' && value.kind === 'date');
}

function valueToText(value: CellValue): string {
  if (value === null || value === undefined) return '';
  if (isDateCell(value)) {
    if (value.value instanceof Date) return value.value.toISOString();
    return value.value ?? '';
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function hasText(value: unknown): boolean {
  return value !== null && value !== undefined && String(value).trim() !== '';
}

function xmlEscape(value: CellValue): string {
  return valueToText(value)
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function columnName(index: number): string {
  let value = index + 1;
  let name = '';
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
}

function dateCell(value: string | Date | null | undefined): DateCell {
  return { kind: 'date', value };
}

function excelSerialDate(
  value: string | Date | null | undefined
): number | null {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  const timestamp = date.getTime();
  if (Number.isNaN(timestamp)) return null;

  return timestamp / 86400000 + 25569;
}

function cellXml(cell: CellValue, reference: string): string {
  if (isDateCell(cell)) {
    const serial = excelSerialDate(cell.value);
    if (serial !== null) {
      return `<c r="${reference}" s="1"><v>${serial}</v></c>`;
    }
  }

  if (typeof cell === 'number' && Number.isFinite(cell)) {
    return `<c r="${reference}"><v>${cell}</v></c>`;
  }

  return `<c r="${reference}" t="inlineStr"><is><t>${xmlEscape(cell)}</t></is></c>`;
}

function sheetDimension(rows: SheetRows): string {
  const rowCount = Math.max(rows.length, 1);
  const columnCount = Math.max(...rows.map((row) => row.length), 1);
  return `A1:${columnName(columnCount - 1)}${rowCount}`;
}

function sheetXml(rows: SheetRows): string {
  const columnCount = Math.max(...rows.map((row) => row.length), 1);
  const cols = Array.from({ length: columnCount }, (_, index) => {
    const width = index === 0 ? 12 : Math.min(index < 10 ? 24 : 32, 42);
    const col = index + 1;
    return `<col min="${col}" max="${col}" width="${width}" customWidth="1"/>`;
  }).join('');
  const body = rows
    .map((row, rowIndex) => {
      const cells = row
        .map((cell, cellIndex) => {
          const reference = `${columnName(cellIndex)}${rowIndex + 1}`;
          return cellXml(cell, reference);
        })
        .join('');
      return `<row r="${rowIndex + 1}">${cells}</row>`;
    })
    .join('');
  const autoFilter =
    rows.length > 1 ? `<autoFilter ref="${sheetDimension(rows)}"/>` : '';

  return [
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
    `<dimension ref="${sheetDimension(rows)}"/>`,
    '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
    `<cols>${cols}</cols>`,
    `<sheetData>${body}</sheetData>`,
    autoFilter,
    '</worksheet>',
  ].join('');
}

function workbookXml(sheets: SheetDefinition[]): string {
  const sheetItems = sheets
    .map(
      (sheet, index) =>
        `<sheet name="${xmlEscape(sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`
    )
    .join('');
  return [
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
    `<sheets>${sheetItems}</sheets>`,
    '</workbook>',
  ].join('');
}

function workbookRelsXml(sheets: SheetDefinition[]): string {
  const sheetRels = sheets
    .map(
      (_sheet, index) =>
        `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`
    )
    .join('');
  return [
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    sheetRels,
    `<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>`,
    '</Relationships>',
  ].join('');
}

function contentTypesXml(sheets: SheetDefinition[]): string {
  const sheetTypes = sheets
    .map(
      (_sheet, index) =>
        `<Override PartName="/xl/worksheets/sheet${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`
    )
    .join('');
  return [
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
    '<Default Extension="xml" ContentType="application/xml"/>',
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    sheetTypes,
    '</Types>',
  ].join('');
}

const ROOT_RELS =
  '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
  '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
  '</Relationships>';

const STYLES_XML =
  '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
  '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
  '<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm"/></numFmts>' +
  '<fonts count="1"><font><sz val="11"/><name val="Aptos"/></font></fonts>' +
  '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>' +
  '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
  '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
  '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>' +
  '</styleSheet>';

function makeFieldColumns(fields: CustomField[], userTypes: UserType[]) {
  const nameCounts = fields.reduce<Record<string, number>>((counts, field) => {
    counts[field.name] = (counts[field.name] ?? 0) + 1;
    return counts;
  }, {});

  return [...fields]
    .sort(
      (left, right) =>
        (left.user_type_id ?? -1) - (right.user_type_id ?? -1) ||
        (left.display_order ?? 0) - (right.display_order ?? 0) ||
        left.name.localeCompare(right.name)
    )
    .map((field) => {
      const scopedType = userTypes.find(
        (type) => type.id === field.user_type_id
      );
      const scope = scopedType?.name ?? 'All users';
      const header =
        nameCounts[field.name] > 1
          ? `Profile: ${field.name} (${scope})`
          : `Profile: ${field.name}`;
      return { field, header, scope };
    });
}

function getIdentityStatus(
  user: UserRosterExportUser,
  identity: UserRosterIdentity | undefined
): string {
  if (
    identity?.status === 'ready' &&
    (user.name_encrypted?.ciphertext !== undefined ||
      user.email_encrypted?.ciphertext !== undefined)
  ) {
    return 'Decrypted';
  }
  if (identity?.name || identity?.email) return 'Decrypted';
  if (user.name || user.email) return 'Plaintext legacy';
  if (user.name_encrypted?.ciphertext || user.email_encrypted?.ciphertext) {
    if (identity?.status === 'failed') return 'Decryption failed';
    if (identity?.status === 'unavailable') return 'Locked';
    return 'Locked';
  }
  return 'Missing';
}

function userProfileValue(
  user: UserRosterExportUser,
  field: CustomField,
  profileValues: Record<string, string | null | undefined>
): string {
  if (
    field.user_type_id !== null &&
    field.user_type_id !== undefined &&
    field.user_type_id !== user.user_type_id
  ) {
    return MISSING_VALUE;
  }

  const fieldName = field.name;
  if (Object.prototype.hasOwnProperty.call(profileValues, fieldName)) {
    const decrypted = profileValues[fieldName];
    return decrypted === null || decrypted === undefined
      ? MISSING_VALUE
      : String(decrypted);
  }
  const plaintext = user.fields?.[fieldName];
  if (hasText(plaintext)) return String(plaintext);
  if (user.fields_encrypted?.[fieldName]?.ciphertext) return LOCKED_VALUE;
  return MISSING_VALUE;
}

function applicableRequiredFields(
  user: UserRosterExportUser,
  fields: CustomField[]
): CustomField[] {
  return fields.filter(
    (field) =>
      field.required &&
      (field.user_type_id === null ||
        field.user_type_id === undefined ||
        field.user_type_id === user.user_type_id)
  );
}

function missingRequiredFields(
  user: UserRosterExportUser,
  fields: CustomField[],
  profileValues: Record<string, string | null | undefined>
): string[] {
  return applicableRequiredFields(user, fields)
    .filter((field) => !hasText(userProfileValue(user, field, profileValues)))
    .map((field) => field.name);
}

function buildUsersRows(
  users: UserRosterExportUser[],
  input: UserRosterWorkbookInput
): SheetRows {
  const fieldColumns = makeFieldColumns(
    input.onboardingFields,
    input.userTypes
  );
  const headers = [
    'User ID',
    'User Approval',
    'Name',
    'Email',
    'User Type',
    'Created At',
    'Nostr Pubkey',
    'Identity Status',
    'Required Profile Complete',
    'Missing Required Fields',
    ...fieldColumns.map((column) => column.header),
  ];

  return [
    headers,
    ...users.map((user) => {
      const identity = input.identities[user.id];
      const profileValues = input.profileValues[user.id] ?? {};
      const missing = missingRequiredFields(
        user,
        input.onboardingFields,
        profileValues
      );
      const nameWasDecrypted =
        identity?.status === 'ready' &&
        user.name_encrypted?.ciphertext !== undefined;
      const emailWasDecrypted =
        identity?.status === 'ready' &&
        user.email_encrypted?.ciphertext !== undefined;
      const name = nameWasDecrypted
        ? (identity.name ?? MISSING_VALUE)
        : identity?.name ||
          user.name ||
          (user.name_encrypted?.ciphertext ? LOCKED_VALUE : MISSING_VALUE);
      const email = emailWasDecrypted
        ? (identity.email ?? MISSING_VALUE)
        : identity?.email ||
          user.email ||
          (user.email_encrypted?.ciphertext ? LOCKED_VALUE : MISSING_VALUE);
      const userType =
        user.user_type?.name ??
        input.userTypes.find((type) => type.id === user.user_type_id)?.name ??
        'Global';

      return [
        user.id,
        user.approved ? 'Approved' : 'Pending',
        name,
        email,
        userType,
        dateCell(user.created_at),
        user.pubkey ?? '',
        getIdentityStatus(user, identity),
        missing.length === 0 ? 'Yes' : 'No',
        missing.join(', '),
        ...fieldColumns.map((column) =>
          userProfileValue(user, column.field, profileValues)
        ),
      ];
    }),
  ];
}

function buildUserTypesRows(input: UserRosterWorkbookInput): SheetRows {
  return [
    [
      'User Type ID',
      'Name',
      'Description',
      'Display Order',
      'Total Users',
      'Approved Users',
      'Pending Users',
    ],
    ...input.userTypes.map((type) => {
      const users = input.users.filter((user) => user.user_type_id === type.id);
      return [
        type.id,
        type.name,
        type.description ?? '',
        type.display_order ?? '',
        users.length,
        users.filter((user) => user.approved).length,
        users.filter((user) => !user.approved).length,
      ];
    }),
    [
      'Global',
      'Global',
      'Users without a User Type',
      '',
      input.users.filter((user) => user.user_type_id === null).length,
      input.users.filter((user) => user.user_type_id === null && user.approved)
        .length,
      input.users.filter((user) => user.user_type_id === null && !user.approved)
        .length,
    ],
  ];
}

function buildFieldDictionaryRows(input: UserRosterWorkbookInput): SheetRows {
  const fieldColumns = makeFieldColumns(
    input.onboardingFields,
    input.userTypes
  );
  return [
    [
      'Export Column',
      'Onboarding Question',
      'User Type Scope',
      'Field Type',
      'Required',
      'Encrypted',
      'Included In Chat Context',
      'Display Order',
    ],
    ...fieldColumns.map(({ field, header, scope }) => [
      header,
      field.name,
      scope,
      field.type,
      Boolean(field.required),
      field.encryption_enabled ?? true,
      field.include_in_chat ?? false,
      field.display_order ?? '',
    ]),
  ];
}

function buildExportNotesRows(
  input: UserRosterWorkbookInput,
  includesDecryptedValues: boolean
): SheetRows {
  return [
    ['Property', 'Value'],
    ['Source', 'Enclave User Roster Export'],
    ['Exported At', input.exportedAt.toISOString()],
    ['Exported By', input.exportedBy ?? 'Admin'],
    ['Users Exported', input.users.length],
    [
      'Pending Approval Users',
      input.users.filter((user) => !user.approved).length,
    ],
    ['Includes Decrypted Browser Values', includesDecryptedValues],
    ['Copied Export Notice', COPIED_EXPORT_NOTICE],
    [
      'Privacy Note',
      'Encrypted values are included only when locally decrypted by the Admin browser. Raw ciphertext is not included.',
    ],
  ];
}

function includesDecryptedValues(input: UserRosterWorkbookInput): boolean {
  return (
    Object.values(input.identities).some(
      (identity) =>
        identity?.status === 'ready' ||
        Boolean(identity?.name) ||
        Boolean(identity?.email)
    ) ||
    Object.values(input.profileValues).some(
      (values) =>
        Object.keys(values).length > 0 || Object.values(values).some(hasText)
    )
  );
}

function buildSheets(
  input: UserRosterWorkbookInput,
  hasDecryptedValues: boolean
): SheetDefinition[] {
  return [
    { name: 'Users', rows: buildUsersRows(input.users, input) },
    {
      name: 'Pending Approval',
      rows: buildUsersRows(
        input.users.filter((user) => !user.approved),
        input
      ),
    },
    { name: 'User Types', rows: buildUserTypesRows(input) },
    { name: 'Field Dictionary', rows: buildFieldDictionaryRows(input) },
    {
      name: 'Export Notes',
      rows: buildExportNotesRows(input, hasDecryptedValues),
    },
  ];
}

const textEncoder = new TextEncoder();

function encode(text: string): Uint8Array {
  return textEncoder.encode(text);
}

let crcTable: Uint32Array | null = null;

function makeCrcTable(): Uint32Array {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) {
    let value = i;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[i] = value >>> 0;
  }
  return table;
}

function crc32(data: Uint8Array): number {
  const table = crcTable ?? makeCrcTable();
  crcTable = table;
  let crc = 0xffffffff;
  for (const byte of data) {
    crc = table[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function writeUint16(view: DataView, offset: number, value: number): void {
  view.setUint16(offset, value, true);
}

function writeUint32(view: DataView, offset: number, value: number): void {
  view.setUint32(offset, value >>> 0, true);
}

function concat(parts: Uint8Array[]): Uint8Array {
  const size = parts.reduce((total, part) => total + part.length, 0);
  const output = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) {
    output.set(part, offset);
    offset += part.length;
  }
  return output;
}

function zipStored(
  entries: Array<{ name: string; data: Uint8Array }>
): Uint8Array {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;

  for (const entry of entries) {
    const name = encode(entry.name);
    const checksum = crc32(entry.data);

    const localHeader = new Uint8Array(30 + name.length);
    const localView = new DataView(localHeader.buffer);
    writeUint32(localView, 0, 0x04034b50);
    writeUint16(localView, 4, 20);
    writeUint16(localView, 6, 0);
    writeUint16(localView, 8, 0);
    writeUint16(localView, 10, 0);
    writeUint16(localView, 12, 0);
    writeUint32(localView, 14, checksum);
    writeUint32(localView, 18, entry.data.length);
    writeUint32(localView, 22, entry.data.length);
    writeUint16(localView, 26, name.length);
    writeUint16(localView, 28, 0);
    localHeader.set(name, 30);
    localParts.push(localHeader, entry.data);

    const centralHeader = new Uint8Array(46 + name.length);
    const centralView = new DataView(centralHeader.buffer);
    writeUint32(centralView, 0, 0x02014b50);
    writeUint16(centralView, 4, 20);
    writeUint16(centralView, 6, 20);
    writeUint16(centralView, 8, 0);
    writeUint16(centralView, 10, 0);
    writeUint16(centralView, 12, 0);
    writeUint16(centralView, 14, 0);
    writeUint32(centralView, 16, checksum);
    writeUint32(centralView, 20, entry.data.length);
    writeUint32(centralView, 24, entry.data.length);
    writeUint16(centralView, 28, name.length);
    writeUint16(centralView, 30, 0);
    writeUint16(centralView, 32, 0);
    writeUint16(centralView, 34, 0);
    writeUint16(centralView, 36, 0);
    writeUint32(centralView, 38, 0);
    writeUint32(centralView, 42, offset);
    centralHeader.set(name, 46);
    centralParts.push(centralHeader);

    offset += localHeader.length + entry.data.length;
  }

  const centralDirectory = concat(centralParts);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  writeUint32(endView, 0, 0x06054b50);
  writeUint16(endView, 4, 0);
  writeUint16(endView, 6, 0);
  writeUint16(endView, 8, entries.length);
  writeUint16(endView, 10, entries.length);
  writeUint32(endView, 12, centralDirectory.length);
  writeUint32(endView, 16, offset);
  writeUint16(endView, 20, 0);

  return concat([...localParts, centralDirectory, end]);
}

function xlsxBytes(sheets: SheetDefinition[]): Uint8Array {
  const entries = [
    { name: '[Content_Types].xml', data: encode(contentTypesXml(sheets)) },
    { name: '_rels/.rels', data: encode(ROOT_RELS) },
    { name: 'xl/workbook.xml', data: encode(workbookXml(sheets)) },
    {
      name: 'xl/_rels/workbook.xml.rels',
      data: encode(workbookRelsXml(sheets)),
    },
    { name: 'xl/styles.xml', data: encode(STYLES_XML) },
    ...sheets.map((sheet, index) => ({
      name: `xl/worksheets/sheet${index + 1}.xml`,
      data: encode(sheetXml(sheet.rows)),
    })),
  ];
  return zipStored(entries);
}

function timestampForFilename(date: Date): string {
  return date
    .toISOString()
    .replace(/[-:]/g, '')
    .replace(/\.\d{3}Z$/, 'Z');
}

export function buildUserRosterWorkbook(
  input: UserRosterWorkbookInput
): UserRosterWorkbook {
  const decrypted = includesDecryptedValues(input);
  const sheets = buildSheets(input, decrypted);
  const bytes = xlsxBytes(sheets);
  const blobBuffer = new ArrayBuffer(bytes.length);
  new Uint8Array(blobBuffer).set(bytes);
  const blob = new Blob([blobBuffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });

  return {
    blob,
    filename: `enclave_users_${timestampForFilename(input.exportedAt)}.xlsx`,
    includesDecryptedValues: decrypted,
  };
}
