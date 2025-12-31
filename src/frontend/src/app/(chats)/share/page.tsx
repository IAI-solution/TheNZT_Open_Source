'use client';

import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { cn } from '@/lib/utils';
import Markdown from '@/components/markdown/Markdown';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
// import Markdown from "@/app/test/component/StreamingTextTracker"
import {
  ChevronDown,
  FileDown,
  FileText,
  Loader2,
  MoveUp,
  Paperclip,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { SearchMode, useMessageStore } from '@/store/useZustandStore';
import { axiosInstance } from '@/services/axiosInstance';
import { PiMarkdownLogo } from 'react-icons/pi';
import { toast } from 'sonner';

import Header from '@/components/layout/Header';
import FinanceChart, { IFinanceData } from '@/components/charts/FinanaceChart';
import { AnimatePresence, motion } from 'framer-motion';
import Image from 'next/image';
import ApiServices from '@/services/ApiServices';
// import { ChatSharingDialog } from "./ChatSharingDialog";
import { uniqueId } from 'lodash';
// import FilePreviewDialog from "./DocumentPreviewModal";
import Citation from '../chat/component/Citation';
import FilePreviewDialog from '../chat/component/DocumentPreviewModal';
import Sources from '../chat/component/Sources';
import CopyButton from '@/components/markdown/CopyButton';
import { VscFilePdf } from 'react-icons/vsc';
import { BsFiletypeDocx } from 'react-icons/bs';
import { IoFlagOutline } from 'react-icons/io5';
import { RxDotsHorizontal } from 'react-icons/rx';
import { HiThumbDown, HiThumbUp } from 'react-icons/hi';
import FeedbackDialog from '@/app/(chats)/chat/component/FeedbackModal';
import { SettingsDropdown } from '@/components/ui/mode-selection';
import { TfiArrowUp } from 'react-icons/tfi';
import { IMessage, IPreviewFileData, IUploadFile } from '../chat/component/SpecificChat';
import { useIsMobile } from '@/hooks/use-is-mobile';

const SpecificChat = () => {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [open, setOpen] = useState(false);
  const [currentTickerSymbol, setCurrentTickerSymbol] = useState('');
  const setMessage = useMessageStore((state) => state.setMessage);
  const setDocumentsIds = useMessageStore((state) => state.setDocuments);
  // State for UI rendering
  const [messages, setMessages] = useState<IMessage[]>([]);
  const [query, setQuery] = useState('');
  const [queryHeading, setQueryHeading] = useState('');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [messageId, setMessageId] = useState('');
  const [currentMessageIdx, setCurrentMessageIdx] = useState(0);
  const [chartDataByMessage, setChartDataByMessage] = useState<Record<string, IFinanceData[]>>({});
  const [financeChartModal, setFinanceChartModal] = useState(false);
  const [financeChartModalData, setFinanceChartModalData] = useState<IFinanceData[]>([]);
  const [openSpecificChart, setOpenSpecificChart] = useState<string[]>([]);
  const [currentCanvasMessageIdx, setCurrentCanvasMessageIdx] = useState(0);
  const [openCanvas, setOpenCanvas] = useState(false);

  const isMobile = useIsMobile();

  const handleOpenSpecificChart = useCallback(
    (key: string) => {
      if (openSpecificChart.includes(key)) {
        setOpenSpecificChart((prev) => prev.filter((item) => item !== key));
      } else {
        setOpenSpecificChart((prev) => [...prev, key]);
      }
    },
    [openSpecificChart]
  );

  const docRef = useRef<HTMLInputElement | null>(null);

  // Refs for DOM elements and mutable values
  const chatDivRef = useRef<HTMLDivElement>(null);
  const latestQueryRef = useRef<HTMLDivElement | null>(null);
  const [reportMessageId, setReportMessageId] = useState<string | null>(null);
  const [reportResponseId, setReportResponseId] = useState<string | null>(null);

  const [openFeedbackModal, setOpenFeedbackModal] = useState(false);

  const [toggleResearchData, setToggleResearchData] = useState<string[]>([]);

  const [showSpecificMap, setShowSpecificMap] = useState<string[]>([]);
  const [showSpecificChartLoader, setShowSpecificChartLoader] = useState<string[]>([]);

  // Store agent selection
  const setSearchMode = useMessageStore((state) => state.setSearchMode);
  const currentSearchMode = useMessageStore((state) => state.searchMode);

  const [uploadedFileData, setUploadedFileData] = useState<IUploadFile[] | []>([]);

  const isReplacingRef = useRef(false);

  const [openPreviewDialog, setOpenPreviewDialog] = useState(false);
  const [currentPreviewFile, setCurrentPreviewFile] = useState<IPreviewFileData | null>(null);

  const [isNotificationEnabled, setIsNotificationEnabled] = useState(false);
  // const [isStopGeneratingResponse, setIsStopGeneratingResponse] = useState(false);

  const MAX_HEIGHT = uploadedFileData.length > 3 ? 302 : uploadedFileData.length > 0 ? 247 : 200;
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null);
  // const abortControllerRef = useRef<AbortController | null>(null);
  const prevMessagesLength = useRef(0);

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
  }, [query]);

  useEffect(() => {
    messages.forEach((message) => {
      const chartArray = Array.isArray(message.chart_data) ? message.chart_data : [];

      chartArray.forEach((chart, index) => {
        const symbol = chart?.realtime?.symbol ?? '';
        if (!symbol) return;
        const key = `${message.message_id}-${symbol}`;
        if (
          messages[0].message_id === message.message_id &&
          index === 0 &&
          openSpecificChart.length === 0
        ) {
          setOpenSpecificChart([key]);
        }
        if (!chartDataByMessage[key]) {
          setChartDataByMessage((prev) => ({
            ...prev,
            [key]: [chart], // array of IFinanceData
          }));
        }
      });
    });
  }, [messages]);

  useEffect(() => {
    const checkNotificationPermission = () => {
      try {
        if ('Notification' in window) {
          const permission = Notification.permission;
          setIsNotificationEnabled(permission === 'granted');
        } else {
          console.log('Notifications not supported');
          setIsNotificationEnabled(false);
        }
      } catch (error) {
        console.error('Error checking notification permission:', error);
        setIsNotificationEnabled(false);
      }
    };

    checkNotificationPermission();
  }, []);

  // Fetch messages if initialMessageData is not available
  const getMessages = async (id: string, accessType: string) => {
    try {
      const result =
        accessType === 'session'
          ? await ApiServices.getSharedCoversationData(id)
          : await ApiServices.getSharedMessageData(id);

      let newMessages: IMessage[] = [];

      if (result.data.message_list.length === 0) {
        router.push('/');
        toast.error(`Unable to load conversation ${id}`);
        return;
      }

      // Update the heading based on the last human query
      const lastMessage = result.data.message_list[result.data.message_list.length - 1];
      setQueryHeading(lastMessage.human_input.user_query);

      result.data.message_list.forEach((message: any, index: number) => {
        // Add user message
        newMessages.push({
          message_id: message.message_id,
          query: message.human_input.user_query,
        });

        newMessages[index].message_id = message.message_id;
        newMessages[index].query = message.human_input.user_query;

        if (message.response) {
          newMessages[index].response = {
            response_id: message.response.id,
            agent_name: message.response.agent_name,
            content: message.response.content,
          };
        }

        if (message.canvas_response&&Object.keys(message.canvas_response).length !== 0) {
          newMessages[index].canvas_response = {
            canvas_response_id: message.canvas_response.document_id,
            agent_name: 'deep-research-agent',
            canvas_version_data: [
              {
                version_number: message.canvas_response.version_number,
                content: message.canvas_response.final_content,
              },
            ],
          };

          newMessages[index].canvas_preview = {
            message_id: message.message_id,
            content: message.canvas_response.preview,
          };
        }

        if (message.research) {
          newMessages[index].research = message.research;
        }

        if (message.sources) {
          newMessages[index].sources = message.sources;
        }

        if (message.stock_chart) {
          newMessages[index].chart_data = message.stock_chart;
        }

        if (message.feedback) {
          newMessages[index].feedback = message.feedback;
        }
        if (message.doc_ids && message.doc_ids.length > 0) {
          newMessages[index].files = message.doc_ids;
        }

        // Add research message if exists
      });

      setMessages(newMessages);
    } catch (error) {
      console.error(error);
      router.push('/');
      toast.error(`Unable to load conversation ${id}`);
    }
  };

  // On component mount, check for session and initialize

  useEffect(() => {
    // Skip the full reload logic if we're just replacing the URL
    if (isReplacingRef.current) {
      isReplacingRef.current = false; // Reset for next time
      return;
    }

    let sessionIdFromParams = '';
    let accessType = '';

    if (searchParams.get('conversation')) {
      sessionIdFromParams = searchParams.get('conversation') || '';
      accessType = 'session';
    } else if (searchParams.get('message')) {
      sessionIdFromParams = searchParams.get('message') || '';
      accessType = 'message';
    }

    // Check if sessionIdFromParams is valid
    if (
      sessionIdFromParams &&
      (sessionIdFromParams.length === 36 || sessionIdFromParams.length === 41)
    ) {
      setSessionId(sessionIdFromParams);
      getMessages(sessionIdFromParams, accessType);
    } else {
      router.push('/');
      toast.error(`Unable to load conversation ${query}`);
    }
  }, [searchParams]);

  useEffect(() => {
    if (messages.length > prevMessagesLength.current) {
      if (latestQueryRef.current) {
        latestQueryRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }
    prevMessagesLength.current = messages.length;
  }, [messages]);

  // Toggle expand for research items
  const toggleExpand = (messageId: string, index: number) => {
    const itemId = `${messageId}-${index}`;

    setExpanded((prev) => {
      if (prev.includes(itemId)) {
        return prev.filter((id, index) => id !== itemId);
      } else {
        return [...prev, itemId];
      }
    });
  };

  const handleToggleResearchData = (messageId: string) => {
    setToggleResearchData((prev) => {
      if (prev.includes(messageId)) {
        return prev.filter((id) => id !== messageId);
      } else {
        return [...prev, messageId];
      }
    });
  };

  const handleShowSpecificMap = (messageId: string, isShown: boolean) => {
    if (isShown) {
      setShowSpecificMap((prev) => {
        return prev.filter((id) => id !== messageId);
      });
    } else {
      setShowSpecificMap((prev) => {
        return [...prev, messageId];
      });
    }
  };

  // Send a message and update state/ref synchronously
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

  const handleOpen = (idx: number) => {
    setOpen(true);
    setCurrentMessageIdx(idx);
  };

  async function handleMonthlyStockChartData(
    period: string,
    message_id: string,
    exchange: string,
    symbol: string
  ) {
    setCurrentTickerSymbol(symbol);
    setShowSpecificChartLoader((prev) => {
      const uniqueId = `${message_id}-${symbol}`;
      return [...prev, uniqueId];
    });
    try {
      const response = await axiosInstance.post('/stock_data', {
        period: period,
        message_id: message_id,
        exchange_symbol: exchange,
        ticker: symbol,
      });

      const messageIndex = messages.findIndex(
        (message) => message.message_id === response.data.message_id
      );

      if (messageIndex !== -1) {
        setMessages((prevMessages) => {
          const updatedMessage = [...prevMessages];
          updatedMessage[messageIndex] = {
            ...updatedMessage[messageIndex],
            chart_data: response.data.stock_data,
          };

          const messageIndexInChartData = updatedMessage[messageIndex].chart_data?.findIndex(
            (chartData) => chartData.realtime?.symbol === symbol
          );
          console.log('messageIndexInChartData', messageIndexInChartData);
          if (
            updatedMessage[messageIndex].chart_data &&
            messageIndexInChartData !== undefined &&
            messageIndexInChartData >= 0
          ) {
            updatedMessage[messageIndex].chart_data[messageIndexInChartData] =
              response.data.stock_data;
          }
          return updatedMessage;
        });
      }
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      setCurrentTickerSymbol('');
      setShowSpecificChartLoader((prev) => {
        const uniqueId = `${message_id}-${symbol}`;
        return messageId ? prev.filter((id) => id !== uniqueId) : prev;
      });
    }
  }

  const handleFeedbackResponse = async (
    messageId: string,
    responseId: string,
    action: 'like' | 'dislike'
  ) => {
    const currentMessage = messages.find((msg) => msg.message_id === messageId);
    if (!currentMessage) return;

    const originalFeedback = currentMessage.feedback; // 1. Store the original state

    // Determine the new state based on the action
    let newFeedbackState: 'yes' | 'no' | null = null;
    let apiPayload: boolean | null = null;

    if (action === 'like') {
      if (originalFeedback?.liked === 'yes') {
        // If already liked, undo it
        newFeedbackState = null;
        apiPayload = null;
      } else {
        // Otherwise, like it
        newFeedbackState = 'yes';
        apiPayload = true;
      }
    } else {
      // action === 'dislike'
      if (originalFeedback?.liked === 'no') {
        // If already disliked, undo it
        newFeedbackState = null;
        apiPayload = null;
      } else {
        // Otherwise, dislike it
        newFeedbackState = 'no';
        apiPayload = false;
      }
    }

    // 2. Update the UI right away for a fast experience
    setMessages((prev) =>
      prev.map((msg) =>
        msg.message_id === messageId
          ? { ...msg, feedback: { ...msg.feedback, liked: newFeedbackState } }
          : msg
      )
    );

    try {
      // 3. Wait for the API call to finish
      await axiosInstance.put('/response-feedback', {
        message_id: messageId,
        response_id: responseId,
        liked: apiPayload,
      });

      // EDIT: Added toaster messages on successful feedback
      if (newFeedbackState === 'yes') {
        toast.success('Thank you for your positive feedback!');
      } else if (newFeedbackState === 'no') {
        toast.info('Thank you for your feedback.');
      }
    } catch (error) {
      console.error('Error sending feedback:', error);
      toast.error('Could not save your feedback.');
      // 4. If the API fails, change the UI back to how it was
      setMessages((prev) =>
        prev.map((msg) =>
          msg.message_id === messageId ? { ...msg, feedback: originalFeedback } : msg
        )
      );
    }
  };

  const handleReportDownload = async (messageId: string, format: string) => {
    try {
      const result = await ApiServices.exportResponse(messageId, format);
      const base64Data = result.file_content_64;
      const fileName = result.filename;

      // Validate base64 string
      if (!base64Data || typeof base64Data !== 'string') {
        throw new Error('Invalid base64 data received from server');
      }

      try {
        // Convert base64 to Blob
        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);

        // Use appropriate MIME type based on format
        const mimeType =
          format === 'pdf'
            ? 'application/pdf'
            : format === 'docx'
              ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
              : 'text/markdown';

        const blob = new Blob([byteArray], { type: mimeType });

        // Create object URL and download via anchor
        const url = URL.createObjectURL(blob);
        const downloadLink = document.createElement('a');
        downloadLink.href = url;
        downloadLink.download = fileName;
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
        URL.revokeObjectURL(url);
      } catch (decodeError) {
        throw new Error('Failed to decode base64 data: Invalid encoding');
      }
    } catch (error: any) {
      const errorMessage =
        error.response?.data?.detail || 'Something went wrong while downloading the file';
      toast.error(errorMessage);
      console.error('Download error:', error);
    }
  };

  const requestNotificationPermission = async () => {
    // Check if notifications are supported
    if (!('Notification' in window)) {
      toast.error('This browser does not support desktop notification');
      return false;
    }

    // If already granted, return true
    if (Notification.permission === 'granted') {
      console.log('✅ Permission already granted');
      setIsNotificationEnabled(true);
      return true;
    }

    // If denied, inform user
    if (Notification.permission === 'denied') {
      toast.error('Notifications are blocked. Please enable them in your browser settings.');
      return false;
    }

    try {
      console.log('🔄 Requesting permission from user...');
      const permission = await Notification.requestPermission();

      if (permission === 'granted') {
        console.log('✅ Permission granted!');
        setIsNotificationEnabled(true);
        return true;
      } else if (permission === 'denied') {
        toast.error('Notification permission denied');
        return false;
      } else {
        toast.info('Notification permission dismissed');
        return false;
      }
    } catch (error) {
      toast.error('Error requesting notification permission');
      return false;
    }
  };

  const handleNotification = async () => {
    try {
      const permission = await requestNotificationPermission();

      if (permission) {
        console.log('✅ Creating notification...');

        const notification = new Notification('🚀 Thanks!', {
          body: 'You will be notified when response is generated.',
          icon: '/icons/bell_icon.svg',
          badge: '/icons/bell_icon.svg',
          requireInteraction: false,
          tag: 'new-45343435',
        });

        // Optional: click handler
        notification.onclick = () => {
          console.log('🔔 Notification clicked');
          window.focus();
          notification.close();
        };

        // Optional: error handler
        notification.onerror = (error) => {
          console.error('❌ Notification error:', error);
        };

        console.log('✅ Notification created successfully');
      } else {
        console.log('❌ Permission not granted, cannot create notification');
      }
    } catch (error) {
      console.error('❌ Error in handleNotification:', error);
      toast.error('Error creating notification');
    }
  };

  const handleNotify = (e: React.MouseEvent) => {
    e.stopPropagation();
    console.log('🖱️ Button clicked - requesting notification');
    handleNotification();
  };

  const handleModalOpen = useCallback(
    (key: string) => {
      setFinanceChartModal(true);
      setFinanceChartModalData(chartDataByMessage[key]);
    },
    [chartDataByMessage]
  );

  const handleOpenFeedbackModal = (messageId: string, responseId: string) => {
    setReportMessageId(messageId);
    setReportResponseId(responseId);
    setOpenFeedbackModal(true);
    document.body.style.pointerEvents = 'auto';
  };

  const getResponsiveClasses = useCallback(
    (openCanvas: boolean) => {
      if (openCanvas) {
        // Container query classes for when canvas is open
        return {
          chatContainer:
            'w-full cq-2xl:max-w-full mx-auto cq-md:px-6 px-4 cq-xl:max-w-3xl cq-lg:max-w-3xl flex flex-col flex-grow overflow-y-auto',
          messageContainer: 'w-full message-container grid grid-cols-1 cq-2xl:grid-cols-10',
          leftColumn: 'flex-grow w-full mb-4 cq-lg:pr-5 cq-2xl:col-span-6 col-span-1',
          rightColumn:
            'mt-8 cq-2xl:block hidden cq-lg:ml-10 cq-2xl:col-span-4 col-span-1 lg:mb-0 mb-8',
          mobileCharts: 'my-4 cq-2xl:hidden block overflow-y-auto',
          mobileMap: 'my-4 cq-2xl:hidden block',
          inputContainer:
            'w-full cq-2xl:max-w-full mx-auto cq-xl:max-w-3xl cq-lg:max-w-3xl grid grid-cols-1 cq-2xl:grid-cols-10 mt-auto fixed bottom-0 box-border bg-[var(--primary-main-bg)] cq-md:px-6 px-4 pb-[20px] sm:relative',
          inputColumn: 'cq-2xl:col-span-6 cq-lg:pr-5',
        };
      } else {
        // Regular responsive classes for when canvas is closed
        return {
          chatContainer:
            'w-full 2xl:max-w-full mx-auto sm:px-6 pl-4 pr-2 xl:max-w-3xl lg:max-w-3xl flex flex-col flex-grow overflow-y-auto',
          messageContainer: 'w-full message-container grid grid-cols-1 2xl:grid-cols-10',
          leftColumn: 'flex-grow w-full mb-4 lg:pr-5 2xl:col-span-6 col-span-1',
          rightColumn: 'mt-8 2xl:block hidden lg:ml-10 2xl:col-span-4 col-span-1 lg:mb-0 mb-8',
          mobileCharts: 'my-4 2xl:hidden block overflow-y-auto',
          mobileMap: 'my-4 2xl:hidden block',
          inputContainer:
            'w-full 2xl:max-w-full mx-auto xl:max-w-3xl lg:max-w-3xl grid grid-cols-1 2xl:grid-cols-10 mt-auto fixed bottom-0 box-border bg-[var(--primary-main-bg)] sm:px-6 px-4 pb-[20px] sm:relative',
          inputColumn: '2xl:col-span-6 lg:pr-5',
        };
      }
    },
    [openCanvas]
  );

  // const handleChatSharingModal = () => {
  //   setOpenChatSharingModal(true);
  // };

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
  //       toast.error('sorry, you can not upload more than 5 files in a single query');
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
  //     } catch (error: any) {
  //       toast.error(
  //         error?.response?.data?.detail || 'something, went wrong, Please try again later'
  //       );

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
    console.log('Opening file dialog for:', fileId, fileName, fileType);
    setCurrentPreviewFile({ fileName, fileType, generatedFileId: fileId });
    setOpenPreviewDialog(true);
  };

  const handleOpenCanvas = (idx: number) => {
    setCurrentCanvasMessageIdx(idx);
    setOpenCanvas(!openCanvas);
  };

  // const stopGeneratingResponse = async () => {

  //   try {
  //     setIsStopGeneratingResponse(true);
  //     const response = await ApiServices.handleStopGeneratingResponse(sessionId, messageId);
  //     toast.success("Response generation stopped successfully");
  //     if (abortControllerRef.current) {
  //       abortControllerRef.current.abort();
  //       abortControllerRef.current = null;
  //       setIsProcessing(false);
  //       setMessages((prev) => {
  //         const updatedMessages = [...prev];

  //         const currentMessageIdx = updatedMessages.findIndex((message) => message.message_id === messageId);

  //         if (currentMessageIdx !== -1) {
  //           updatedMessages[currentMessageIdx] = { ...updatedMessages[currentMessageIdx], isCancelled: true }
  //         }

  //         return updatedMessages;
  //       })
  //       if (eventSourceRef.current) {
  //         eventSourceRef.current.close();
  //         eventSourceRef.current = null;
  //       }
  //     }
  //   } catch (error: any) {
  //     toast.error(error.response?.data?.detail || "Failed to stop response generation");
  //   } finally {
  //     setIsStopGeneratingResponse(false);
  //   }

  // }

  // const handleElaborateResponse = (exampleStatus: string) => {
  //   setElaborateWithExample(exampleStatus);
  //   setShowElaborateSummarize(false);
  //   setIsProcessing(true);

  //   const updatedQueryHeading = `Elaborate: ${queryHeading}`;
  //   const isExample = exampleStatus === "with" ? true : false;

  //   setQueryHeading(updatedQueryHeading);
  //   startEventStream2(
  //     updatedQueryHeading,
  //     "",
  //     false,
  //     false,
  //     "summarizer",
  //     true,
  //     isExample
  //   )
  // }

  // const handleSummarizeResponse = (exampleStatus: string) => {
  //   setSummarizeWithExample(exampleStatus);
  //   setShowElaborateSummarize(false);
  //   setIsProcessing(true);
  //   const isExample = exampleStatus === "with" ? true : false;

  //   const updatedQueryHeading = `Summarize: ${queryHeading}`;
  //   setQueryHeading(updatedQueryHeading);
  //   startEventStream2(
  //     updatedQueryHeading,
  //     "",
  //     false,
  //     false,
  //     "summarizer",
  //     false,
  //     isExample
  //   )
  // }

  // Add this line right before your return statement
  const classes = getResponsiveClasses(openCanvas);

  return (
    <div className="w-full flex h-[calc(100vh-4.75rem)] lg:h-screen">
      {/* Add 'content-container' class to enable container queries */}
      <div
        data-detect={openCanvas ? 'canvas-open' : undefined}
        className={cn(
          'w-full h-full pt-0 lg:pt-0 pb-4 lg:pb-6 lg:pr-8 flex flex-col bg-[var(--primary-main-bg)]',
          openCanvas && 'content-container'
        )}
      >
        <Header heading={queryHeading} />

        <div className="lg:ml-8 lg:px-0 mt-2 w-full flex flex-col flex-grow overflow-hidden">
          <div
            ref={chatDivRef}
            className={cn(
              classes.chatContainer,
              { 'pb-[62dvh]': isProcessing },
              { 'pb-[100px]': !isProcessing }
            )}
          >
            {messages.length > 0 &&
              messages.map((message, index) => {
                return (
                  <div
                    key={index}
                    ref={index === messages.length - 1 ? latestQueryRef : null}
                    className={classes.messageContainer}
                  >
                    <div className={classes.leftColumn}>
                      {/* Render if message.query exists */}

                      <div className="my-8">
                        {message.files && message.files.length > 0 && (
                          <div className="flex justify-start items-center gap-2 mb-2">
                            {message.files.map((fileData, index) => (
                              <div
                                key={fileData.generatedFileId + index}
                                onClick={() => {
                                  handleOpenFileDialog(
                                    fileData.generatedFileId,
                                    fileData.fileName,
                                    fileData.fileType
                                  );
                                }}
                                className={cn(
                                  'group flex cursor-pointer items-start flex-wrap gap-2.5 rounded-lg bg-[#EBEBD7] px-2.5 py-2 relative'
                                )}
                              >
                                <div className="size-[1.875rem] w-fit max-w-48 rounded-md bg-white p-1.5 flex items-center justify-center">
                                  <FileText
                                    strokeWidth={1.5}
                                    className="text-primary-main size-4"
                                  />
                                </div>

                                <div className="flex flex-col max-w-60">
                                  <p className="text-xs w-full truncate font-semibold text-black">
                                    {fileData.fileName}
                                  </p>
                                  <span className="text-[10px] truncate text-[#8F8D8D] font-medium">
                                    {fileData.fileType.split('/')[1].toUpperCase()}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {message.query && (
                          <div className="flex justify-end">
                            <div className="w-fit ml-16">
                              <h2
                                className="p-4 rounded-bl-[12px] rounded-br-[12px] rounded-tl-[12px] rounded-tr-none bg-[var(--primary-text-bg)] text-left text-base font-medium leading-6 text-[#191919]"
                                style={{ fontFamily: 'Schibsted Grotesk' }}
                              >
                                {message.query}
                              </h2>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Render if message.research exists and has length > 0 */}
                      {message.research && message.research.length > 0 && (
                        <div className="max-w-full rounded-xl border border-[#F3F0E8]">
                          <div
                            className={`bg-[var(--primary-main-bg)] sm:px-4 px-2 sm:py-5 py-3 border border-[rgba(16,40,34,0.06)] ${!toggleResearchData.includes(message.message_id)
                              ? 'rounded-xl'
                              : 'rounded-t-xl'
                              }`}
                          >
                            {isProcessing && message.message_id === messageId ? (
                              // Processing State
                              <div className="flex w-full flex-col gap-y-3">
                                {/* Top row: text on left, buttons on right */}
                                <div
                                  onClick={() => handleToggleResearchData(message.message_id)}
                                  className="flex w-full cursor-pointer items-center justify-between"
                                >
                                  <div className="flex items-center gap-x-2">
                                    <div role="status" className="flex-shrink-0">
                                      <Image
                                        src="/images/loader.svg"
                                        alt="loader"
                                        priority
                                        height={20}
                                        width={20}
                                        className="animate-spin sm:size-5 size-4"
                                      />
                                    </div>
                                    <p className="sm:text-base text-sm font-semibold text-[#181818]">
                                      {(message.research &&
                                        message.research[message.research.length - 1]
                                          ?.agent_name) ||
                                        'Agent'}{' '}
                                      is working
                                    </p>
                                  </div>
                                  <div className="flex flex-shrink-0 items-center gap-x-2">
                                    {!isNotificationEnabled && (
                                      <>
                                        <button
                                          onClick={handleNotify}
                                          className="hidden items-center gap-x-1 py-1.5 px-3.5 text-sm font-semibold text-primary-main sm:flex"
                                        >
                                          <Image
                                            src="/icons/bell_icon.svg"
                                            alt="bell"
                                            height={20}
                                            width={20}
                                            priority
                                            className="size-5"
                                          />
                                          <span className="text-[#954767] text-[16px] font-medium not-italic leading-none font-schibsted">
                                            Notify Me
                                          </span>
                                        </button>
                                        <button className="flex-shrink-0 sm:hidden block pl-2">
                                          <Image
                                            onClick={handleNotify}
                                            src="/icons/bell_icon.svg"
                                            alt="bell"
                                            height={20}
                                            width={20}
                                            priority
                                            className="size-5 cursor-pointer"
                                          />
                                        </button>
                                      </>
                                    )}
                                    <ChevronDown
                                      className={`text-black sm:size-5 size-5 flex-shrink-0 transition-transform ${toggleResearchData.includes(message.message_id)
                                        ? 'transform rotate-180'
                                        : ''
                                        }`}
                                    />
                                  </div>
                                  <p className="sm:text-base text-sm font-semibold text-[#181818]">
                                    Agent is working
                                  </p>
                                </div>
                                <div className="flex flex-shrink-0 items-center gap-x-2">
                                  {!isNotificationEnabled && (
                                    <>
                                      <button
                                        onClick={handleNotify}
                                        className="hidden items-center gap-x-1 py-1.5 px-3.5 text-sm font-semibold text-primary-main sm:flex"
                                      >
                                        <Image
                                          src="/icons/bell_icon.svg"
                                          alt="bell"
                                          height={20}
                                          width={20}
                                          priority
                                          className="size-5"
                                        />
                                        <span className="text-[#4B9770] text-[16px] font-medium not-italic leading-none font-schibsted">
                                          Notify Me
                                        </span>
                                      </button>
                                      <button className="flex-shrink-0 sm:hidden block pl-2">
                                        <Image
                                          onClick={handleNotify}
                                          src="/icons/bell_icon.svg"
                                          alt="bell"
                                          height={20}
                                          width={20}
                                          priority
                                          className="size-5 cursor-pointer"
                                        />
                                      </button>
                                    </>
                                  )}
                                  <ChevronDown
                                    className={`text-black sm:size-5 size-5 flex-shrink-0 transition-transform ${toggleResearchData.includes(message.message_id)
                                      ? 'transform rotate-180'
                                      : ''
                                      }`}
                                  />
                                </div>
                              </div>
                            ) : (
                              // Completed or Error State
                              <div
                                onClick={() => handleToggleResearchData(message.message_id)}
                                className="flex w-full cursor-pointer items-center justify-between"
                              >
                                <div className="flex min-w-0 items-center sm:gap-x-3 gap-x-2">
                                  {message.isCancelled ? (
                                    <p className="sm:text-base text-sm font-semibold">
                                      Response Cancelled
                                    </p>
                                  ) : message.error ? (
                                    <p className="sm:text-base text-sm font-semibold">
                                      Error in generating response
                                    </p>
                                  ) : (
                                    <>
                                      <div role="status" className="flex-shrink-0">
                                        <Image
                                          src="/images/loader.svg"
                                          alt="loader"
                                          priority
                                          height={20}
                                          width={20}
                                          className="sm:size-5 size-4"
                                        />
                                      </div>
                                      <p className="truncate sm:text-base text-sm font-semibold">
                                        {message.heading || "All done! Let's dive into the results"}
                                      </p>
                                    </>
                                  )}
                                </div>
                                <div className="flex flex-shrink-0 items-center gap-x-2">
                                  {message.response_time && (
                                    <p className="whitespace-nowrap font-schibsted text-[10px] font-medium capitalize leading-normal not-italic text-[#818181] sm:text-sm">
                                      <span className="hidden sm:inline">Took </span>
                                      {message.response_time}
                                    </p>
                                  )}

                                  <ChevronDown
                                    className={`text-black sm:size-5 size-5 flex-shrink-0 transition-transform ${toggleResearchData.includes(message.message_id)
                                      ? 'transform rotate-180'
                                      : ''
                                      }`}
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                          <AnimatePresence mode="wait">
                            {toggleResearchData.includes(message.message_id) && (
                              <motion.div
                                initial={{
                                  height: 0,
                                  opacity: 0,
                                }}
                                animate={{
                                  height: 'auto',
                                  opacity: 1,
                                }}
                                exit={{
                                  height: 0,
                                  opacity: 0,
                                }}
                                transition={{
                                  height: {
                                    duration: 0.4,
                                    ease: [0.04, 0.62, 0.23, 0.98], // Custom cubic-bezier for smooth motion
                                  },
                                  opacity: {
                                    duration: 0.25,
                                    ease: 'easeInOut',
                                  },
                                }}
                                style={{ overflow: 'hidden' }} // Crucial for smooth height animation
                                className="w-full flex flex-col bg-[#F3F1EE] rounded-b-xl"
                              >
                                <div className="p-4 bg-[var(--primary-text-bg)]">
                                  <div className="relative">
                                    {/* Timeline line */}
                                    <div className="absolute left-[0.9675rem] top-4 bottom-3 w-0.5 bg-[#4B9770]/10" />

                                    {message.research &&
                                      message.research.map((researchData, idx) => {
                                        const itemId = `${message.message_id}-${idx}`;
                                        const activeMessage = message.message_id === messageId;
                                        const isLastResearchItem =
                                          idx === (message.research?.length || 0) - 1;
                                        const isExpanded = expanded.includes(itemId);
                                        const showLoader =
                                          activeMessage && isLastResearchItem && isProcessing;

                                        return (
                                          <div
                                            key={idx}
                                            onClick={() => toggleExpand(message.message_id, idx)}
                                            className="cursor-pointer overflow-hidden flex items-start px-3 rounded-md gap-x-2 py-1 first:pt-0 last:pb-0 hover:bg-white/50"
                                          >
                                            {/* Dot or loader */}
                                            <div className="relative flex-shrink-0 mt-1.5">
                                              {showLoader ? (
                                                <div className="loader" />
                                              ) : (
                                                <div className="w-2 h-2 rounded-[4px] bg-[rgba(16,40,34,0.41)]" />
                                              )}
                                            </div>

                                            {/* Research content */}
                                            <div className="w-full overflow-hidden">
                                              <div className="flex w-full justify-between items-start gap-x-2">
                                                <motion.div
                                                  initial={false}
                                                  animate={{
                                                    height:
                                                      isExpanded || showLoader ? 'auto' : '1.25rem',
                                                  }}
                                                  className="text-sm font-medium leading-tight overflow-hidden"
                                                  style={{ overflow: 'hidden' }}
                                                >
                                                  <Markdown
                                                    allowHtml={true}
                                                    latex={false}
                                                    className=""
                                                    isProcessing={isProcessing}
                                                  // currentData={currentResponseChunkData}
                                                  >
                                                    {researchData.title}
                                                  </Markdown>
                                                </motion.div>
                                                <ChevronDown
                                                  size={18}
                                                  className={`text-gray-500 flex-shrink-0 transition-transform duration-300 ease-in-out ${isExpanded || showLoader
                                                    ? 'transform rotate-180'
                                                    : ''
                                                    }`}
                                                />
                                              </div>
                                            </div>
                                          </div>
                                        );
                                      })}
                                  </div>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      )}


                      <div
                        className={cn(
                          classes.mobileCharts,
                          message.chart_data && message.chart_data.length > 5 && 'h-[400px]'
                        )}
                      >
                        {message.chart_data && message.chart_data.length > 0 && (
                          <>
                            {message.chart_data.map((individualChart) => {
                              const key = `${message.message_id}-${individualChart?.realtime?.symbol}`;
                              return (
                                <div key={key}>
                                  <FinanceChart
                                    messageId={message.message_id}
                                    chart_data={chartDataByMessage[key]}
                                    loading={showSpecificChartLoader.includes(key)}
                                    setCurrentTickerSymbol={setCurrentTickerSymbol}
                                    setShowSpecificChartLoader={setShowSpecificChartLoader}
                                    handleModalOpen={handleModalOpen}
                                    isModalView={false}
                                    openSpecificChart={openSpecificChart}
                                    handleOpenSpecificChart={handleOpenSpecificChart}
                                    financeChartModal={financeChartModal}
                                  />
                                </div>
                              );
                            })}
                          </>
                        )}
                      </div>

                      {message.response && (
                        <>
                          <div className="py-2" id={message.message_id}>
                            {(() => {
                              const content = message.response.content.toString();
                              // Detect if content contains RTL characters (Arabic, Hebrew, Persian, etc.)
                              const isRtl = /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F]/.test(
                                content
                              );

                              return (
                                <div
                                  className={cn({ 'font-[Arial]': isRtl }, 'message-response')}
                                  dir={isRtl ? 'rtl' : 'ltr'}
                                >
                                  <Markdown
                                    allowHtml={true}
                                    latex={false}
                                    isProcessing={isProcessing}
                                  >
                                    {content}
                                  </Markdown>
                                </div>
                              );
                            })()}

                            {message.response && (
                              <div className="my-6 flex flex-1 flex-col self-stretch justify-end items-start gap-6">
                                {/* Suggestion Box (Elaborate/Summarize) */}

                                {/* ADD THIS NEW WRAPPER AND DIVIDER BELOW IT */}
                                <div className="w-full space-y-6">
                                  <div className="h-px w-full bg-[#E9E5D2]"></div>

                                  <div className="flex w-full flex-col items-start justify-between gap-4 rounded-[12px] md:flex-row md:items-center">
                                    <div>
                                      {message.sources && message.sources.length > 0 && (
                                        <div className="">
                                          <Sources
                                            data={message.sources}
                                            onHandleCitationData={() => handleOpen(index)}
                                          />
                                        </div>
                                      )}
                                    </div>

                                    {/* Right side - Other action buttons */}
                                    {messages.length - 1 !== index && (
                                      <div className="flex items-center gap-4">
                                        <div className="flex items-center text-sm gap-x-4">
                                          <CopyButton
                                            strokeWidth={1.5}
                                            content={message.response.content}
                                            id={message.message_id}
                                            className="cursor-pointer size-[20px] text-black"
                                          />
                                          <DropdownMenu>
                                            <DropdownMenuTrigger>
                                              <TooltipProvider>
                                                <Tooltip>
                                                  <TooltipTrigger asChild>
                                                    <FileDown
                                                      strokeWidth={1.5}
                                                      className="cursor-pointer size-[20px]"
                                                    />
                                                  </TooltipTrigger>
                                                  <TooltipContent>
                                                    <p>Download</p>
                                                  </TooltipContent>
                                                </Tooltip>
                                              </TooltipProvider>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent className="">
                                              <DropdownMenuItem
                                                onClick={() =>
                                                  handleReportDownload(message.message_id, 'pdf')
                                                }
                                                className="flex gap-x-1.5 items-center"
                                              >
                                                <VscFilePdf /> PDF
                                              </DropdownMenuItem>
                                              <DropdownMenuItem
                                                onClick={() =>
                                                  handleReportDownload(message.message_id, 'md')
                                                }
                                                className="flex gap-x-1.5 items-center"
                                              >
                                                <PiMarkdownLogo /> Markdown
                                              </DropdownMenuItem>
                                              <DropdownMenuItem
                                                onClick={() =>
                                                  handleReportDownload(message.message_id, 'docx')
                                                }
                                                className="flex gap-x-1.5 items-center"
                                              >
                                                <BsFiletypeDocx /> DOCX
                                              </DropdownMenuItem>
                                            </DropdownMenuContent>
                                          </DropdownMenu>

                                          <>
                                            <TooltipProvider>
                                              <Tooltip>
                                                <TooltipTrigger asChild>
                                                  <button
                                                    onClick={() =>
                                                      handleFeedbackResponse(
                                                        message.message_id,
                                                        message.response?.response_id || '',
                                                        'like' // Use string 'like' to handle toggling
                                                      )
                                                    }
                                                    className="focus:outline-none"
                                                    aria-label={
                                                      message.feedback?.liked === 'yes'
                                                        ? 'Unlike'
                                                        : 'Like'
                                                    }
                                                  >
                                                    {message.feedback?.liked === 'yes' ? (
                                                      // Use filled icon with a primary color when liked
                                                      <HiThumbUp
                                                        strokeWidth={1.5}
                                                        className="size-[20px] cursor-pointer text-[#2E2E2E]"
                                                      />
                                                    ) : (
                                                      // Use outline icon when not liked
                                                      <ThumbsUp
                                                        strokeWidth={1.5}
                                                        className="size-[20px] cursor-pointer text-black"
                                                      />
                                                    )}
                                                  </button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                  <p>
                                                    {message.feedback?.liked === 'yes'
                                                      ? 'Liked'
                                                      : 'Like'}
                                                  </p>
                                                </TooltipContent>
                                              </Tooltip>
                                            </TooltipProvider>

                                            <TooltipProvider>
                                              <Tooltip>
                                                <TooltipTrigger asChild>
                                                  <button
                                                    onClick={() =>
                                                      handleFeedbackResponse(
                                                        message.message_id,
                                                        message.response?.response_id || '',
                                                        'dislike' // Use string 'dislike' to handle toggling
                                                      )
                                                    }
                                                    className="focus:outline-none"
                                                    aria-label={
                                                      message.feedback?.liked === 'no'
                                                        ? 'Remove dislike'
                                                        : 'Dislike'
                                                    }
                                                  >
                                                    {message.feedback?.liked === 'no' ? (
                                                      // Use filled icon with a primary color when disliked
                                                      <HiThumbDown
                                                        strokeWidth={1.5}
                                                        className="size-[20px] cursor-pointer text-[#2E2E2E]"
                                                      />
                                                    ) : (
                                                      // Use outline icon when not disliked
                                                      <ThumbsDown
                                                        strokeWidth={1.5}
                                                        className="size-[20px] cursor-pointer text-black"
                                                      />
                                                    )}
                                                  </button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                  <p>
                                                    {message.feedback?.liked === 'no'
                                                      ? 'Disliked'
                                                      : 'Dislike'}
                                                  </p>
                                                </TooltipContent>
                                              </Tooltip>
                                            </TooltipProvider>
                                          </>

                                          <DropdownMenu>
                                            <DropdownMenuTrigger>
                                              <RxDotsHorizontal className="text-base" size={20} />
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent>
                                              <DropdownMenuItem
                                                onClick={() =>
                                                  handleOpenFeedbackModal(
                                                    message.message_id,
                                                    message.response?.response_id || ''
                                                  )
                                                }
                                              >
                                                <IoFlagOutline size={20} />
                                                Report
                                              </DropdownMenuItem>
                                            </DropdownMenuContent>
                                          </DropdownMenu>
                                        </div>
                                      </div>
                                    )}
                                    {messages.length - 1 === index && !isProcessing && (
                                      <div className="flex items-center gap-4 order-2 md:order-none">
                                        <div className="flex items-center text-sm gap-x-4">
                                          <CopyButton
                                            strokeWidth={1.5}
                                            content={message.response.content}
                                            id={message.message_id}
                                            className="cursor-pointer size-[20px] text-black"
                                          />
                                          <DropdownMenu>
                                            <DropdownMenuTrigger>
                                              <TooltipProvider>
                                                <Tooltip>
                                                  <TooltipTrigger asChild>
                                                    <FileDown
                                                      strokeWidth={1.5}
                                                      className="cursor-pointer size-[20px]"
                                                    />
                                                  </TooltipTrigger>
                                                  <TooltipContent>
                                                    <p>Download</p>
                                                  </TooltipContent>
                                                </Tooltip>
                                              </TooltipProvider>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent className="">
                                              <DropdownMenuItem
                                                onClick={() =>
                                                  handleReportDownload(message.message_id, 'pdf')
                                                }
                                                className="flex gap-x-1.5 items-center"
                                              >
                                                <VscFilePdf /> PDF
                                              </DropdownMenuItem>
                                              <DropdownMenuItem
                                                onClick={() =>
                                                  handleReportDownload(message.message_id, 'md')
                                                }
                                                className="flex gap-x-1.5 items-center"
                                              >
                                                <PiMarkdownLogo /> Markdown
                                              </DropdownMenuItem>
                                              <DropdownMenuItem
                                                onClick={() =>
                                                  handleReportDownload(message.message_id, 'docx')
                                                }
                                                className="flex gap-x-1.5 items-center"
                                              >
                                                <BsFiletypeDocx /> DOCX
                                              </DropdownMenuItem>
                                            </DropdownMenuContent>
                                          </DropdownMenu>

                                          <>
                                            <TooltipProvider>
                                              <Tooltip>
                                                <TooltipTrigger asChild>
                                                  <button
                                                    onClick={() =>
                                                      handleFeedbackResponse(
                                                        message.message_id,
                                                        message.response?.response_id || '',
                                                        'like' // Use string 'like' to handle toggling
                                                      )
                                                    }
                                                    className="focus:outline-none"
                                                    aria-label={
                                                      message.feedback?.liked === 'yes'
                                                        ? 'Unlike'
                                                        : 'Like'
                                                    }
                                                  >
                                                    {message.feedback?.liked === 'yes' ? (
                                                      // Use filled icon with a primary color when liked
                                                      <HiThumbUp
                                                        strokeWidth={1.5}
                                                        className="size-[20px] cursor-pointer text-[#2E2E2E]"
                                                      />
                                                    ) : (
                                                      // Use outline icon when not liked
                                                      <ThumbsUp
                                                        strokeWidth={1.5}
                                                        className="size-[20px] cursor-pointer text-black"
                                                      />
                                                    )}
                                                  </button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                  <p>
                                                    {message.feedback?.liked === 'yes'
                                                      ? 'Liked'
                                                      : 'Like'}
                                                  </p>
                                                </TooltipContent>
                                              </Tooltip>
                                            </TooltipProvider>

                                            <TooltipProvider>
                                              <Tooltip>
                                                <TooltipTrigger asChild>
                                                  <button
                                                    onClick={() =>
                                                      handleFeedbackResponse(
                                                        message.message_id,
                                                        message.response?.response_id || '',
                                                        'dislike' // Use string 'dislike' to handle toggling
                                                      )
                                                    }
                                                    className="focus:outline-none"
                                                    aria-label={
                                                      message.feedback?.liked === 'no'
                                                        ? 'Remove dislike'
                                                        : 'Dislike'
                                                    }
                                                  >
                                                    {message.feedback?.liked === 'no' ? (
                                                      // Use filled icon with a primary color when disliked
                                                      <HiThumbDown
                                                        strokeWidth={1.5}
                                                        className="size-[20px] cursor-pointer text-[#2E2E2E]"
                                                      />
                                                    ) : (
                                                      // Use outline icon when not disliked
                                                      <ThumbsDown
                                                        strokeWidth={1.5}
                                                        className="size-[20px] cursor-pointer text-black"
                                                      />
                                                    )}
                                                  </button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                  <p>
                                                    {message.feedback?.liked === 'no'
                                                      ? 'Disliked'
                                                      : 'Dislike'}
                                                  </p>
                                                </TooltipContent>
                                              </Tooltip>
                                            </TooltipProvider>
                                          </>

                                          <DropdownMenu>
                                            <DropdownMenuTrigger>
                                              <RxDotsHorizontal className="text-base" size={20} />
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent>
                                              <DropdownMenuItem
                                                onClick={() =>
                                                  handleOpenFeedbackModal(
                                                    message.message_id,
                                                    message.response?.response_id || ''
                                                  )
                                                }
                                              >
                                                <IoFlagOutline size={20} />
                                                Report
                                              </DropdownMenuItem>
                                            </DropdownMenuContent>
                                          </DropdownMenu>
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </>
                      )}
                    </div>

                    <div className={classes.rightColumn}>
                      <div className="flex gap-x-5 items-center">
                        {message.chart_data && message.chart_data.length > 0 && (
                          <div
                            onClick={() => handleShowSpecificMap(message.message_id, true)}
                            className={cn('p-3 px-1 cursor-pointer', {
                              'border-0 border-b-2 border-b-[rgba(16,40,34,0.08)]':
                                !showSpecificMap.includes(message.message_id),
                            })}
                          >
                            <p className="text-sm font-semibold leading-normal text-[#0A0A0A]">
                              Visual Data{' '}
                              <span className="relative top-[-0.2em] ml-1 text-[10px] font-medium leading-normal text-[#2E2E2E]">
                                (Graphs and Charts)
                              </span>
                            </p>
                          </div>
                        )}

                        {message.map_data && (
                          <div
                            onClick={() => handleShowSpecificMap(message.message_id, false)}
                            className={cn('p-3 px-1 cursor-pointer', {
                              'border-0 border-b-2 border-b-primary-main':
                                showSpecificMap.includes(message.message_id) || !message.chart_data,
                            })}
                          >
                            <p className="text-sm leading-normal font-semibold text-primary-main">
                              Visual Data{' '}
                              <span className="text-[10px] mr-0.5 leading-normal font-semibold text-[#A09F9B]">
                                (Maps)
                              </span>
                            </p>
                          </div>
                        )}
                      </div>

                      <div
                        className={`mt-4 md:pr-6 overflow-y-auto ${message.chart_data && message.chart_data.length > 5 && 'h-[900px]'}`}
                      >
                        {message.chart_data && message.chart_data.length > 0 && (
                          <>
                            {message.chart_data.map((individualChart) => {
                              const key = `${message.message_id}-${individualChart?.realtime?.symbol}`;

                              return (
                                <div key={key}>
                                  <FinanceChart
                                    messageId={message.message_id}
                                    chart_data={chartDataByMessage[key]}
                                    loading={showSpecificChartLoader.includes(
                                      `${message.message_id}-${currentTickerSymbol}`
                                    )}
                                    setCurrentTickerSymbol={setCurrentTickerSymbol}
                                    setShowSpecificChartLoader={setShowSpecificChartLoader}
                                    handleModalOpen={handleModalOpen}
                                    isModalView={false}
                                    openSpecificChart={openSpecificChart}
                                    handleOpenSpecificChart={handleOpenSpecificChart}
                                    financeChartModal={financeChartModal}
                                  />
                                </div>
                              );
                            })}
                          </>
                        )}
                      </div>

                      {/* {message.map_data && message.map_data.length > 0 && (
                        <div className={classes.mobileMap}>
                          <MapView hexagonData={message.map_data} />
                        </div>
                      )} */}
                    </div>
                  </div>
                );
              })}
          </div>

          <div className={classes.inputContainer}>
            <div className={classes.inputColumn}>
              <div className="flex flex-col items-start sm:p-4 p-3 rounded-[1rem] border-2 focus-within:border-transparent focus-within:bg-[var(--primary-text-bg)] transition overflow-hidden">
                {uploadedFileData.length > 0 && (
                  <div className="flex flex-wrap items-start gap-2 mb-6">
                    {uploadedFileData.map((fileData, index) => (
                      <div
                        key={fileData.fileId}
                        onClick={() => {
                          console.log(
                            'Opening file dialog for:',
                            fileData.generatedFileId,
                            fileData.fileName,
                            fileData.type
                          );
                          handleOpenFileDialog(
                            fileData.generatedFileId,
                            fileData.fileName,
                            fileData.type
                          );
                        }}
                        className={cn(
                          'group flex cursor-pointer items-start flex-wrap gap-2.5 rounded-lg bg-[#B2C2A6] px-2.5 py-2 transition-colors duration-200 relative',
                          fileData.isUploading && 'disabled'
                        )}
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
                            handleRemoveFile(fileData.fileId);
                          }}
                          className="rounded-full p-0.5"
                          aria-label="Remove file"
                        >
                          <X className="size-5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <textarea
                  autoFocus
                  ref={textAreaRef}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    handleAutoTextAreaResize(e.target);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && query.trim() && !isProcessing) {
                      sendMessage();
                    }
                  }}
                  value={query}
                  placeholder="Ask Follow Up Questions"
                  className="w-full bg-transparent resize-none placeholder:text-neutral-150 focus:outline-none"
                />

                <div className="flex items-center justify-between w-full mt-2">
                  <div className="flex items-center gap-x-3">
                    

                    {/* <div className="flex items-center gap-x-4">
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

                      <div className="relative group flex items-center">
                        <button onClick={openDocUpload}>
                          <Paperclip className="sm:size-5 size-4" />
                        </button>
                        <div className="absolute z-10 hidden group-hover:block bg-black text-white text-sm px-2 py-1 rounded-md -top-9 left-0 ml-[-1.5rem] sm:ml-[-0.5rem] whitespace-nowrap shadow">
                          Supported: PDF, Excel, TXT
                        </div>
                      </div>
                    </div> */}
                  </div>

                  <div className="flex items-center justify-between">
                    <SettingsDropdown
                      value={currentSearchMode}
                      onValueChange={(value: SearchMode) => {
                        setSearchMode(value);
                      }}
                    />
                    <button
                      disabled={!query.trim() || isProcessing}
                      onClick={() => sendMessage()}
                      className="flex items-center justify-center border border-transparent p-2 size-[2.25rem] rounded-full disabled:bg-[rgba(113,161,141,0.10)] disabled:opacity-90 disabled:text-[#818181] text-white bg-[#4B9770]"
                    >
                      <TfiArrowUp size={20} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>


      {messages[currentMessageIdx]?.sources && messages[currentMessageIdx].sources.length > 0 && (
        <div className="">
          <Citation
            data={messages[currentMessageIdx].sources}
            open={open}
            onOpenChange={() => setOpen(false)}
          />
        </div>
      )}

      <FeedbackDialog
        isOpen={openFeedbackModal}
        messageId={reportMessageId}
        responseId={reportResponseId}
        onOpenChange={setOpenFeedbackModal}
      />
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
  );
};

export default SpecificChat;
