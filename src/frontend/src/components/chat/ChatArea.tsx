'use client';

import { FileText, Loader2, Paperclip, Settings2, X } from 'lucide-react';

import React, { useLayoutEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';
import { SearchMode, useMessageStore } from '@/store/useZustandStore';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { IPreviewFileData, IUploadFile } from '@/app/(chats)/chat/component/SpecificChat';
import { toast } from 'sonner';
import { uniqueId } from 'lodash';
import { TfiArrowUp } from 'react-icons/tfi';
import ApiServices from '@/services/ApiServices';
import FilePreviewDialog from '@/app/(chats)/chat/component/DocumentPreviewModal';
import { SettingsDropdown } from '../ui/mode-selection';

export type researchData = {
  agentName: string;
  title: string;
};

export type Message = {
  content: string | string[];
  sender?: 'user' | 'assistant';
  type?: string;
  actionData?: any;
  researchData?: researchData[] | [];
  messageId?: string;
};

const ChatArea = () => {
  const [query, setQuery] = useState('');
  const router = useRouter();
  const setMessage = useMessageStore((state) => state.setMessage);
  const setDocumentsIds = useMessageStore((state) => state.setDocuments);
  const setSearchMode = useMessageStore((state) => state.setSearchMode);
  const resetSearchMode = useMessageStore((state) => state.resetSearchMode);
  const currentSearchMode = useMessageStore((state) => state.searchMode);
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null);
  const textContainerRef = useRef<HTMLDivElement | null>(null);
  const [uploadedFileData, setUploadedFileData] = useState<IUploadFile[] | []>([]);

  const [defaultPrompts, setDefaultPrompts] = useState<string[] | []>([
    '⚖️ Risk assessment',
    '🌐 Economic indicators',
    '🔍 Market Sentiment',
    '📉 Sector trends',
    '📁 Portfolio strategy',
  ]);
  const [openPreviewDialog, setOpenPreviewDialog] = useState(false);
  const [currentPreviewFile, setCurrentPreviewFile] = useState<IPreviewFileData | null>(null);
  const docRef = useRef<HTMLInputElement | null>(null);
  const MAX_HEIGHT =
    uploadedFileData.length > 3 ? 372 : uploadedFileData.length > 0 ? 260 + 47 : 260;

  const handleAutoTextAreaResize = (ta: HTMLTextAreaElement) => {
    ta.style.height = 'auto';
    const scrollH = ta.scrollHeight;
    const newH = Math.min(scrollH, MAX_HEIGHT);
    ta.style.height = `${newH}px`;
  };

  useLayoutEffect(() => {
    if (textAreaRef.current) {
      handleAutoTextAreaResize(textAreaRef.current);
    }
    resetSearchMode();
  }, []);

  const sendMessage = async () => {
    const message = query.trim();
    const documents = uploadedFileData.map((file) => ({
      fileName: file.fileName,
      fileType: file.type,
      generatedFileId: file.generatedFileId,
    }));
    setDocumentsIds(documents || []);
    setMessage(message);
    setQuery('');
    router.push(`/chat`);
  };

  const handleAgentChange = (value: SearchMode) => {
    setSearchMode(value);
  };

  const openDocUpload = () => {
    if (docRef.current) {
      docRef.current.click();
    }
  };

  // const handleDocUploadChange = async (file: FileList | null) => {
  //   if (file) {
  //     const uploadedfile = file[0];
  //     const maxSize = 2 * 1024 * 1024; // 1MB

  //     if (uploadedfile.size > maxSize) {
  //       toast.error('File size limit exceeded. Please upload files smaller than 2MB.');
  //       return;
  //     }

  //     if (uploadedFileData.length >= 5) {
  //       toast.error('Maximum file upload limit reached.');
  //       return;
  //     }

  //     const fileId = uniqueId();

  //     // Add file to state with uploading status
  //     setUploadedFileData((prev) => {
  //       const fileDetails: IUploadFile = {
  //         fileId: fileId,
  //         fileName: uploadedfile.name,
  //         type: uploadedfile.type,
  //         isUploading: true,
  //         generatedFileId: '',
  //       };
  //       return [...prev, fileDetails];
  //     });

  //     try {
  //       console.log(uploadedfile, 'uploadedfile');
  //       const response = await ApiServices.uploadFiles(uploadedfile);

  //       // Update the specific file's status
  //       setUploadedFileData((prev) => {
  //         // Use 'prev' instead of 'uploadedFileData' to avoid stale closure
  //         const currentUploadedFileIndex = prev.findIndex((file) => file.fileId === fileId);

  //         if (currentUploadedFileIndex === -1) {
  //           console.error('File not found in state', fileId);
  //           return prev; // Return unchanged state if file not found
  //         }

  //         // Create a new array with the updated file
  //         const updatedData = prev.map((file, index) => {
  //           if (index === currentUploadedFileIndex) {
  //             return {
  //               ...file,
  //               isUploading: false,
  //               generatedFileId: response.data.doc_id,
  //             };
  //           }
  //           return file;
  //         });

  //         return updatedData;
  //       });

  //       console.log('response', response);
  //     } catch (error: any) {
  //       console.log('error in file uploading api', error);

  //       // Remove the file from state on error or mark as failed
  //       setUploadedFileData((prev) => {
  //         return prev.filter((file) => file.fileId !== fileId);
  //         // Or alternatively, mark as failed:
  //         // return prev.map(file =>
  //         //   file.fileId === fileId
  //         //     ? { ...file, isUploading: false, uploadError: true }
  //         //     : file
  //         // );
  //       });

  //       toast.error(error.response?.data?.detail || 'Something went wrong');
  //     }
  //   }
  // };

  const handleRemoveFile: (fileIdToRemove: string) => void = (fileIdToRemove) => {
    setUploadedFileData((prev) => {
      return prev.filter((file) => file.fileId !== fileIdToRemove);
    });
  };
  const handleOpenFileDialog = (fileId: string, fileName: string, fileType: string) => {
    setCurrentPreviewFile({ fileName, fileType, generatedFileId: fileId });
    setOpenPreviewDialog(true);
  };

  return (
    <>
      <div className="relative flex items-center justify-center w-full h-[100vh] mt-[-76px] flex-center lg:mt-[0px] overflow-x-hidden bg-[var(--primary-main-bg)]">
        <div className="sm:max-w-4xl w-full h-full xl:px-0 px-5">
          <div className="sm:flex hidden w-full h-full flex-col justify-center items-center">
            <div className={cn(`text-center flex items-center justify-center`)}>
              <h1 className="text-[#0A0A0A] text-center text-[52px] font-normal leading-normal">
                What's on your mind today?
              </h1>
            </div>
            <div className="sm:my-6 w-full box-border pl-[20px] pr-[20px] bg-[var(--primary-main-bg)]">
              <div
                ref={textContainerRef}
                style={{ maxHeight: `${MAX_HEIGHT}px` }}
                className="flex flex-col self-stretch gap-[10px] rounded-[16px] focus-within:bg-[var(--primary-chart-bg)] border border-[#E9E9E9] bg-[var(--primary-main-bg)] pt-[20px] pb-[16px] px-[24px] focus-within:border-primary-main/50 transition active:bg-[var(--primary-chart-bg)]"
              >
                {uploadedFileData.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    {uploadedFileData.map((fileData, index) => (
                      <div
                        onClick={() =>
                          handleOpenFileDialog(
                            fileData.generatedFileId,
                            fileData.fileName,
                            fileData.type
                          )
                        }
                        key={fileData.fileId}
                        className="group flex items-start cursor-pointer flex-wrap gap-2.5 rounded-lg bg-[#B2C2A6] px-2.5 py-2 relative"
                      >
                        <div className="size-[1.875rem] w-fit max-w-48 rounded-md bg-white p-1.5 flex items-center justify-center">
                          {fileData.isUploading ? (
                            <Loader2 className="text-black size-5 animate-spin" />
                          ) : (
                            <FileText strokeWidth={1.5} className="text-black size-4" />
                          )}
                        </div>

                        <div className="flex flex-col max-w-60">
                          <p className="text-xs w-full truncate font-semibold text-black">
                            {fileData.fileName}
                          </p>
                          <span className="text-[10px] truncate text-[#8F8D8D] font-medium">
                            {fileData.type.split('/')[1].toUpperCase()}
                          </span>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            // Add your remove file logic here
                            handleRemoveFile(fileData.fileId);
                          }}
                          className="rounded-full p-0.5"
                          aria-label="Remove file"
                        >
                          <X className="size-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <textarea
                  autoFocus
                  ref={textAreaRef}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    handleAutoTextAreaResize(e.target);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      if (query.trim()) {
                        sendMessage();
                      }
                    }
                  }}
                  placeholder="Ask anything.."
                  className="w-full flex-grow bg-transparent text-[#333131] text-base leading-relaxed font-medium resize-none placeholder:text-neutral-150 focus:outline-none"
                ></textarea>

                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center gap-3">
                   
                    {/* <div className="relative group flex items-center">
                      <button onClick={openDocUpload}>
                        <Paperclip className="sm:size-5 size-4" />
                      </button>
                      <div className="absolute z-10 hidden group-hover:block bg-black text-white text-sm px-2 py-1 rounded-md -top-9 left-0 ml-[-1.5rem] sm:ml-[-0.5rem] whitespace-nowrap shadow">
                        Supported: PDF, Excel, TXT
                      </div>
                    </div>

                    <input
                      accept=".pdf,.txt,.xlsx"
                      onChange={(e) => {
                        handleDocUploadChange(e.target.files);
                        e.target.value = '';
                      }}
                      type="file"
                      ref={docRef}
                      hidden
                    /> */}
                  </div>

                  <div className="flex items-center">
                     <SettingsDropdown value={currentSearchMode} onValueChange={handleAgentChange} />
                    <button
                      disabled={!query}
                      onClick={sendMessage}
                      className="flex items-center justify-center border border-transparent size-[2.25rem] rounded-full disabled:bg-[rgba(113,161,141,0.10)] disabled:opacity-90 disabled:text-[#818181] text-white bg-[#4B9770]"
                    >
                      <TfiArrowUp size={20} />
                    </button>
                  </div>
                </div>
              </div>

              <div className="sm:hidden py-3.5 flex items-center justify-center gap-x-1 text-center text-[10px] tracking-normal font-normal text-[#7E7E7E]">
                <p>
                  Insight Agent may make mistakes — always verify key insights before relying on
                  them.
                </p>
              </div>
            </div>
          </div>

          {/* Mobile View */}

          <div className="sm:hidden flex flex-col h-full">
            <div
              className={cn(
                `text-center flex-grow gap-y-[1.125rem] flex flex-col items-center justify-center`
              )}
            >
              <h1 className="text-primary-dark sm:text-[3.375rem] text-[1.25rem] font-medium leading-tight">
                Ask me anything finance!
              </h1>

              <div className="flex items-center justify-center gap-2 flex-wrap">
                {defaultPrompts.map((prompt, index) => (
                  <button
                    key={index}
                    className="py-2 px-4 text-xs font-medium tracking-wide bg-[var(--primary-main-bg)] rounded-[28px] border border-[#F3ECDA]"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            <div className="sm:my-6 mt-auto w-full fixed bottom-0 left-0 right-0 box-border z-10 bg-[var(--primary-main-bg)] pl-[20px] pr-[20px]">
              <div
                ref={textContainerRef}
                style={{ maxHeight: `${MAX_HEIGHT}px` }}
                className="flex flex-col self-stretch gap-[10px] focus-within:bg-[var(--primary-text-bg)] rounded-[16px] border border-[#E9E9E9] bg-[var(--primary-main-bg)] p-4 focus-within:border-primary-main/50 transition"
              >
                {uploadedFileData.length > 0 && (
                  <div className="flex flex-wrap items-start gap-2 mb-6">
                    {uploadedFileData.map((fileData, index) => (
                      <div
                        onClick={() =>
                          handleOpenFileDialog(
                            fileData.generatedFileId,
                            fileData.fileName,
                            fileData.type
                          )
                        }
                        key={fileData.fileId}
                        className="group flex items-start cursor-pointer flex-wrap gap-2.5 rounded-lg bg-[#B2C2A6] px-2.5 py-2 relative"
                      >
                        <div className="size-[1.875rem] w-fit max-w-48 rounded-md bg-white p-1.5 flex items-center justify-center">
                          {fileData.isUploading ? (
                            <Loader2 className="text-black size-5 animate-spin" />
                          ) : (
                            <FileText strokeWidth={1.5} className="text-black size-4" />
                          )}
                        </div>

                        <div className="flex flex-col max-w-60">
                          <p className="text-xs w-full truncate font-semibold text-black">
                            {fileData.fileName}
                          </p>
                          <span className="text-[10px] truncate text-[#8F8D8D] font-medium">
                            {fileData.type.split('/')[1].toUpperCase()}
                          </span>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            // Add your remove file logic here
                            handleRemoveFile(fileData.fileId);
                          }}
                          className="rounded-full p-0.5"
                          aria-label="Remove file"
                        >
                          <X className="size-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <textarea
                  autoFocus
                  ref={textAreaRef}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    handleAutoTextAreaResize(e.target);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      if (query.trim()) {
                        sendMessage();
                      }
                    }
                  }}
                  placeholder="Ask anything.."
                  className="w-full flex-grow bg-transparent text-base text-[#333131] leading-relaxed font-medium resize-none placeholder:text-neutral-150 focus:outline-none"
                ></textarea>

                <div className="flex items-center justify-between w-full">
                  <div className="flex w-full items-center justify-between">
                    <div className="flex gap-3 items-center">
                     
                      {/* <div className="flex items-center">
                        <input
                          accept=".pdf,.txt,.xlsx"
                          onChange={(e) => {
                            handleDocUploadChange(e.target.files);
                            e.target.value = '';
                          }}
                          type="file"
                          ref={docRef}
                          hidden
                        />

                        <div className="relative group">
                          <button onClick={openDocUpload}>
                            <Paperclip className="sm:size-5 size-4" />
                          </button>
                          <div className="absolute z-10 hidden group-hover:block bg-black text-white text-sm px-2 py-1 rounded-md -top-9 left-0 ml-[-1.5rem] sm:ml-[-0.5rem] whitespace-nowrap shadow">
                            Supported: PDF, Excel, TXT
                          </div>
                        </div>
                      </div> */}
                    </div>

                    <div className='flex '>
                       <SettingsDropdown
                        value={currentSearchMode}
                        onValueChange={handleAgentChange}
                        isMobile
                      />
                      <button
                        disabled={!query}
                        onClick={sendMessage}
                        className="flex items-center justify-center border border-transparent size-[2.25rem] rounded-full disabled:bg-[rgba(113,161,141,0.10)] disabled:opacity-90 disabled:text-[#818181] text-white bg-[#4B9770]"
                      >
                        <TfiArrowUp size={20} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="sm:hidden py-3.5 flex items-center justify-center gap-x-1 text-center text-[10px] tracking-normal font-normal text-[#7E7E7E]">
                <p>
                  Insight Agent may make mistakes — always verify key insights before relying on
                  them.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="sm:block hidden mt-auto absolute bottom-6">
          <div className="flex justify-center items-center ">
            <div className="flex items-center gap-x-8 text-[0.75rem] font-normal text-#020202 justify-center">
              <p>Blog</p>
              {/* <Select>
                <SelectTrigger className="w-fit min-w-28 sm:max-w-36 border-none">
                  <SelectValue placeholder="Select Language" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="English">English</SelectItem>
                </SelectContent>
              </Select> */}
            </div>
          </div>
        </div>

        {currentPreviewFile && (
          <FilePreviewDialog
            open={openPreviewDialog}
            onClose={setOpenPreviewDialog}
            fileId={currentPreviewFile.generatedFileId}
            fileName={currentPreviewFile.fileName}
            fileType={currentPreviewFile.fileType}
          />
        )}
      </div>
    </>
  );
};

export default ChatArea;
