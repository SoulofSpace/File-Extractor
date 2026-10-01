import React from 'react';
import { SearchResultItem } from '../../api/types';
import { FileCard } from './FileCard';

interface FileGridProps {
  files: SearchResultItem[];
  selectedFile: SearchResultItem | null;
  onSelectFile: (file: SearchResultItem) => void;
  onOpenFile: (path: string) => void;
}

export const FileGrid: React.FC<FileGridProps> = ({
  files,
  selectedFile,
  onSelectFile,
  onOpenFile,
}) => {
  if (files.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 p-1">
      {files.map((file) => (
        <FileCard
          key={`${file.file_id}-${file.path}`}
          file={file}
          isSelected={selectedFile?.file_id === file.file_id}
          onSelect={onSelectFile}
          onOpen={onOpenFile}
        />
      ))}
    </div>
  );
};
