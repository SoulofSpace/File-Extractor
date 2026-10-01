export interface CategoryConfig {
  id: string;
  label: string;
  iconName: string;
  hasFormats: boolean;
  formats?: { ext: string; label: string }[];
}

export const CATEGORIES_CONFIG: CategoryConfig[] = [
  {
    id: 'ALL',
    label: 'All',
    iconName: 'LayoutGrid',
    hasFormats: false,
  },
  {
    id: 'DOCUMENT',
    label: 'Documents',
    iconName: 'FileText',
    hasFormats: true,
    formats: [
      { ext: 'pdf', label: 'PDF' },
      { ext: 'docx', label: 'DOCX' },
      { ext: 'doc', label: 'DOC' },
      { ext: 'pptx', label: 'PPTX' },
      { ext: 'ppt', label: 'PPT' },
      { ext: 'xlsx', label: 'XLSX' },
      { ext: 'xls', label: 'XLS' },
      { ext: 'txt', label: 'TXT' },
      { ext: 'csv', label: 'CSV' },
      { ext: 'rtf', label: 'RTF' },
      { ext: 'odt', label: 'ODT' },
      { ext: 'ods', label: 'ODS' },
      { ext: 'md', label: 'Markdown' },
    ],
  },
  {
    id: 'IMAGE',
    label: 'Images',
    iconName: 'Image',
    hasFormats: true,
    formats: [
      { ext: 'jpg', label: 'JPG' },
      { ext: 'jpeg', label: 'JPEG' },
      { ext: 'png', label: 'PNG' },
      { ext: 'webp', label: 'WEBP' },
      { ext: 'gif', label: 'GIF' },
      { ext: 'bmp', label: 'BMP' },
      { ext: 'svg', label: 'SVG' },
      { ext: 'tiff', label: 'TIFF' },
    ],
  },
  {
    id: 'VIDEO',
    label: 'Videos',
    iconName: 'Film',
    hasFormats: true,
    formats: [
      { ext: 'mp4', label: 'MP4' },
      { ext: 'mkv', label: 'MKV' },
      { ext: 'avi', label: 'AVI' },
      { ext: 'mov', label: 'MOV' },
      { ext: 'webm', label: 'WEBM' },
      { ext: 'wmv', label: 'WMV' },
      { ext: 'flv', label: 'FLV' },
    ],
  },
  {
    id: 'AUDIO',
    label: 'Audio',
    iconName: 'Music',
    hasFormats: true,
    formats: [
      { ext: 'mp3', label: 'MP3' },
      { ext: 'wav', label: 'WAV' },
      { ext: 'flac', label: 'FLAC' },
      { ext: 'm4a', label: 'M4A' },
      { ext: 'aac', label: 'AAC' },
      { ext: 'ogg', label: 'OGG' },
    ],
  },
  {
    id: 'CODE',
    label: 'Code',
    iconName: 'Code2',
    hasFormats: true,
    formats: [
      { ext: 'py', label: 'Python (py)' },
      { ext: 'js', label: 'JavaScript (js)' },
      { ext: 'ts', label: 'TypeScript (ts)' },
      { ext: 'tsx', label: 'React TS (tsx)' },
      { ext: 'jsx', label: 'React JS (jsx)' },
      { ext: 'java', label: 'Java' },
      { ext: 'c', label: 'C' },
      { ext: 'cpp', label: 'C++' },
      { ext: 'html', label: 'HTML' },
      { ext: 'css', label: 'CSS' },
      { ext: 'json', label: 'JSON' },
      { ext: 'sql', label: 'SQL' },
    ],
  },
  {
    id: 'ARCHIVE',
    label: 'Archives',
    iconName: 'Archive',
    hasFormats: true,
    formats: [
      { ext: 'zip', label: 'ZIP' },
      { ext: 'rar', label: 'RAR' },
      { ext: '7z', label: '7Z' },
      { ext: 'tar', label: 'TAR' },
      { ext: 'gz', label: 'GZ' },
    ],
  },
];
