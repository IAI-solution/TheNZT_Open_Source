'use client';

import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { cn } from '@/lib/utils';
import Markdown from '@/components/markdown/Markdown';
import { HiThumbDown, HiThumbUp } from 'react-icons/hi';
import { Progress } from '@/components/ui/progress';
import { produce } from 'immer';

import {
  ChevronDown,
  FileDown,
  FileText,
  Loader2,
  Repeat,
  Share2,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import { IoFlagOutline } from 'react-icons/io5';
import { RxDotsHorizontal } from 'react-icons/rx';
import { SearchMode, useMessageStore } from '@/store/useZustandStore';
import { axiosInstance } from '@/services/axiosInstance';
import { PiMarkdownLogo, PiWarningCircleFill } from 'react-icons/pi';
import { VscFilePdf } from 'react-icons/vsc';
import { BsArrowRepeat, BsFiletypeDocx } from 'react-icons/bs';
import { toast } from 'sonner';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import Header from '@/components/layout/Header';
import CopyButton from '@/components/markdown/CopyButton';
import FinanceChart, { IFinanceData } from '@/components/charts/FinanaceChart';
import FeedbackDialog from '@/app/(chats)/chat/component/FeedbackModal';
import { AnimatePresence, motion } from 'framer-motion';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import Sources from './Sources';
import Citation from './Citation';
import Image from 'next/image';
import Cookies from 'js-cookie';
import ApiServices from '@/services/ApiServices';
import { IMapDataPoint } from '@/types/map-view';
import { API_ENDPOINTS } from '@/services/endpoints';
import { logout } from '@/utils/auth';
import MapView from '@/components/maps/MapView';
import { ChatSharingDialog } from './ChatSharingDialog';
import FilePreviewDialog from './DocumentPreviewModal';
import { SettingsDropdown } from '@/components/ui/mode-selection';
import { TfiArrowUp } from 'react-icons/tfi';
import { formatDateWithMicroseconds } from '@/utils/date';
import { ADD_FORM, handlePaginationData } from '@/utils/pagination';
import { useSessionHistoryStore } from '@/store/useSessionHistory';
import { useIsMobile } from '@/hooks/use-is-mobile';
import WaitUntilResponse from '@/components/charts/WaitUntilResponse';
// import { mapData } from "@/data/random_map_data";
// import MapView from "@/app/map-2/page";
// import MapView from "@/components/maps/MapView";

export type researchData = {
  id: string;
  agent_name: string;
  title: string;
};

export type responseData = {
  response_id: string;
  agent_name: string;
  content: string;
};

export type canvasVersionData = {
  version_number: number;
  content: string;
};

export type canvasResponseData = {
  canvas_response_id: string;
  agent_name: string;
  canvas_version_data: canvasVersionData[];
};

export type canvasPreviewData = {
  message_id: string;
  content: string;
};

export type sourcesData = {
  favicon: string;
  title: string;
  domain: string;
  link: string;
  snippet?: string;
};

export interface IMessage {
  message_id: string;
  query: string;
  files?: IPreviewFileData[] | [];
  research?: researchData[];
  response?: responseData;
  canvas_response?: canvasResponseData;
  canvas_preview?: canvasPreviewData;
  related_queries?: string[];
  sources?: sourcesData[];
  chart_data?: IFinanceData[] | [];
  response_time?: string;
  map_data?: IMapDataPoint[] | [];
  error?: boolean;
  isSuggestion?: boolean;
  isElaborate?: boolean;
  isRetry?: boolean;
  isCancelled?: boolean;
  feedback?: {
    liked?: string | null;
  };
  progress?: number;
  agent_name_for_progress?: string;
  heading?: string;
}

export interface IUploadFile {
  fileId: string;
  type: string;
  fileName: string;
  isUploading: boolean;
  generatedFileId: string;
}

export interface IPreviewFileData {
  fileType: string;
  fileName: string;
  generatedFileId: string;
}

const retryOptions = [
  {
    value: 'fast',
    title: 'Lite',
    description: 'Rapid market response and action',
  },
  {
    value: 'agentic-planner',
    title: 'Core',
    description: 'Strategic planning through agentic modeling',
  },
  {
    value: 'agentic-reasoning',
    title: 'Pro',
    description: 'Deep reasoning and scenario simulation',
  },
];

const SpecificChat = () => {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [open, setOpen] = useState(false);
  const [currentTickerSymbol, setCurrentTickerSymbol] = useState('');
  const [showExitConsent, setShowExitConsent] = useState(false);

  // State for UI rendering
  const [messages, setMessages] = useState<IMessage[]>([]);
  const [query, setQuery] = useState('');
  const [queryHeading, setQueryHeading] = useState('');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processingMessageId, setProcessingMessageId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [messageId, setMessageId] = useState('');
  const [currentMessageIdx, setCurrentMessageIdx] = useState(0);
  const initialRef = useRef<boolean | null>(true);

  const docRef = useRef<HTMLInputElement | null>(null);

  const chunkBufferRef = useRef<Record<string, string>>({});
  const chunkCounterRef = useRef<Record<string, number>>({});
  // Refs for DOM elements and mutable values
  const chatDivRef = useRef<HTMLDivElement>(null);
  const latestQueryRef = useRef<HTMLDivElement | null>(null);
  const scrollAnchorRef = useRef<{ scrollTop: number; scrollHeight: number } | null>(null); // Add this line
  const eventSourceRef = useRef<EventSource | null>(null);
  const messageRefs = useRef(new Map<string, HTMLDivElement>());

  const [toggleResearchData, setToggleResearchData] = useState<string[]>([]);

  const [showSpecificMap, setShowSpecificMap] = useState<string[]>([]);
  const [showSpecificChartLoader, setShowSpecificChartLoader] = useState<string[]>([]);

  const [showElaborateSummarize, setShowElaborateSummarize] = useState(false);

  const [reportMessageId, setReportMessageId] = useState<string | null>(null);
  const [reportResponseId, setReportResponseId] = useState<string | null>(null);

  const [openFeedbackModal, setOpenFeedbackModal] = useState(false);
  const [openChatSharingModal, setOpenChatSharingModal] = useState(false);

  const [currentCanvasMessageIdx, setCurrentCanvasMessageIdx] = useState(0);

  // Store agent selection
  const setSearchMode = useMessageStore((state) => state.setSearchMode);
  const currentSearchMode = useMessageStore((state) => state.searchMode);
  const initialMessageData = useMessageStore((state) => state.message);
  const setInitialMessage = useMessageStore((state) => state.setMessage);
  const removeDocuments = useMessageStore((state) => state.removeDocuments);
  const setFinanceChartModalDataa = useMessageStore((state) => state.setFinanceChartModalDataa);
  const [uploadedFileData, setUploadedFileData] = useState<IUploadFile[] | []>([]);

  const isReplacingRef = useRef(false);

  const [openPreviewDialog, setOpenPreviewDialog] = useState(false);
  const [currentPreviewFile, setCurrentPreviewFile] = useState<IPreviewFileData | null>(null);

  const [isNotificationEnabled, setIsNotificationEnabled] = useState(false);
  const [isStopGeneratingResponse, setIsStopGeneratingResponse] = useState(false);

  const [elaborateWithExample, setElaborateWithExample] = useState('with');
  const [summarizeWithExample, setSummarizeWithExample] = useState('with');

  const [sharedMessageId, setSharedMessageId] = useState('');
  const [financeChartModal, setFinanceChartModal] = useState(false);
  const [financeChartModalData, setFinanceChartModalData] = useState<IFinanceData[]>([]);

  const [chartDataByMessage, setChartDataByMessage] = useState<Record<string, IFinanceData[]>>({});
  const [openSpecificChart, setOpenSpecificChart] = useState<string[]>([]);
  const setSessionHistoryData = useSessionHistoryStore((s) => s.setSessionHistoryData);

  const [openCanvas, setOpenCanvas] = useState(false);

  const hasSetDefaultChartRef = useRef(false);

  // Add these persistent maps
  const messageIndexMap = useRef(new Map()); // messageId -> index
  const versionIndexMaps = useRef(new Map()); // messageId -> Map(versionNumber -> in

  const isMobile = useIsMobile();

  // Add this effect to rebuild maps when messages structure changes
  useEffect(() => {
    messageIndexMap.current.clear();
    versionIndexMaps.current.clear();

    messages.forEach((message, index) => {
      messageIndexMap.current.set(message.message_id, index);

      if (message.canvas_response?.canvas_version_data) {
        const versionMap = new Map();
        message.canvas_response.canvas_version_data.forEach((versionData, vIndex) => {
          versionMap.set(versionData.version_number, vIndex);
        });
        versionIndexMaps.current.set(message.message_id, versionMap);
      }
    });
  }, [messages.length]);

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

  const MAX_HEIGHT = uploadedFileData.length > 3 ? 302 : uploadedFileData.length > 0 ? 247 : 200;
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const prevMessagesLength = useRef(0);

  console.log(messages, 'message');

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
        console.log('Error checking notification permission:', error);
        setIsNotificationEnabled(false);
      }
    };

    checkNotificationPermission();
  }, []);

  const handleModalOpen = useCallback(
    (
      key: string,
      messageId: string,
      exchange: string,
      ticker: string,
      chart_session_id: string
    ) => {
      // setFinanceChartModal(true);
      setFinanceChartModalData(chartDataByMessage[key]);
      setFinanceChartModalDataa(chartDataByMessage[key]);
      if (isProcessing) {
        setShowExitConsent(true);
        return;
      }
      setInitialMessage('');
      router.push(
        `/stock_details?sessionId=${sessionId}&messageId=${messageId}&exchange=${exchange}&ticker=${ticker}&chart_session_id=${chart_session_id}`
      );
    },
    [chartDataByMessage, isProcessing]
  );

  // Fetch messages if initialMessageData is not available
  const getMessages = async (sessionId: string) => {
    try {
      const result = await axiosInstance.get('/messages', {
        params: {
          sessionId,
        },
      });

      let newMessages: IMessage[] = [];

      if (result.data.message_list.length === 0) {
        router.push('/');
        toast.error(`Unable to load conversation ${sessionId}`);
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

        console.log(result.data.message_list);

        newMessages[index].message_id = message.message_id;
        newMessages[index].query = message.human_input.user_query;

        if (message.response) {
          newMessages[index].response = {
            response_id: message.response.id,
            agent_name: message.response.agent_name,
            content: message.response.content,
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
        if (
          message.human_input &&
          message.human_input.doc_ids &&
          message.human_input.doc_ids.length > 0
        ) {
          newMessages[index].files = message.human_input.doc_ids;
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

          console.log(message.canvas_response.final_content.length);

          newMessages[index].canvas_preview = {
            message_id: message.message_id,
            content: message.canvas_response.preview,
          };
        }

        if (message.time_taken) {
          newMessages[index].response_time = String(message.time_taken);
        }

        if (message.human_input) {
          newMessages[index].isRetry = message.human_input.retry;
        }

        // Add research message if exists
      });

      setMessages(newMessages);
    } catch (error) {
      console.log(error);
      router.push('/');
      toast.error(`Unable to load conversation ${sessionId}`);
    }
  };

  function sendNotification() {
    if (!('Notification' in window)) {
      console.warn('This browser does not support notification.');
      return;
    }

    if (Notification.permission === 'granted') {
      new Notification('🚀 Hello Insight-Agent user', {
        body: '✅ Your response has been generated',
        icon: '/icons/bell_icon.svg',
        badge: '/icons/bell_icon.svg',
        requireInteraction: false,
        tag: 'web-notification',
      });
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
          new Notification('🚀 Hello Insight-Agent user', {
            body: '✅ Your response has been generated',
            icon: '/icons/bell_icon.svg',
            badge: '/icons/bell_icon.svg',
            requireInteraction: false,
            tag: 'web-notification',
          });
        }
      });
    }
  }

  function updateMessages(data: any) {
    if (data.type === 'response') {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );

        updatedMessages[messageIndex] = {
          ...updatedMessages[messageIndex],
          response: {
            response_id: data.id,
            agent_name: data.agent_name,
            content: data.content,
          },
        };

        return updatedMessages;
      });
    } else if (data.type === 'response-chunk') {
      const messageId = data.message_id;

      // Initialize buffer and counter if not already
      if (!chunkBufferRef.current[messageId]) {
        chunkBufferRef.current[messageId] = '';
        chunkCounterRef.current[messageId] = 0;
      }

      // Append chunk to buffer and increment counter
      chunkBufferRef.current[messageId] += data.content;
      chunkCounterRef.current[messageId] += 1;

      // Update only when counter hits 3
      if (chunkCounterRef.current[messageId] >= 1) {
        const bufferedContent = chunkBufferRef.current[messageId];

        setMessages((prevMessages) => {
          const updatedMessages = [...prevMessages];

          const currentMessageIdx = updatedMessages.findIndex(
            (message) => message.message_id === data.message_id
          );

          const previousContent = updatedMessages[currentMessageIdx].response?.content || '';

          if (currentMessageIdx !== -1) {
            updatedMessages[currentMessageIdx].response = {
              response_id: data.id,
              agent_name: data.agent_name,
              content: previousContent + bufferedContent,
            };
          }

          return updatedMessages;
        });

        // Reset buffer and counter
        chunkBufferRef.current[messageId] = '';
        chunkCounterRef.current[messageId] = 0;
      }
    } else if (data.type === 'canvas-response-chunk') {
      const messageId = data.message_id;

      // Initialize buffer and counter if not already
      // if (!chunkBufferRef.current[messageId]) {
      //   chunkBufferRef.current[messageId] = '';
      //   chunkCounterRef.current[messageId] = 0;
      // }

      // Append chunk to buffer and increment counter
      // chunkBufferRef.current[messageId] += data.content;
      // chunkCounterRef.current[messageId] += 1;

      // Update only when counter hits 3
      // if (chunkCounterRef.current[messageId] >= 1) {

      let bufferedContent: string = '';
      bufferedContent += data.content;

      setMessages(
        produce((draft) => {
          // O(1) - Fast map lookup instead of findIndex
          const messageIndex = messageIndexMap.current.get(messageId);

          if (messageIndex === undefined) return; // Message not found

          const message = draft[messageIndex];

          if (message.canvas_response && message.canvas_response?.canvas_version_data?.length > 0) {
            // O(1) - Fast version lookup instead of findIndex
            const versionMap = versionIndexMaps.current.get(messageId);
            const versionDataIdx = versionMap?.get(data.version_number);

            if (versionDataIdx !== undefined) {
              // O(k) - Only string concatenation cost remains
              const versionData = message.canvas_response.canvas_version_data[versionDataIdx];
              const previousContent = versionData.content || '';
              versionData.content = previousContent + bufferedContent;
            }
          } else {
            // Create new canvas response
            message.canvas_response = {
              canvas_response_id: data.id,
              agent_name: data.agent_name,
              canvas_version_data: [
                {
                  version_number: 1,
                  content: data.content,
                },
              ],
            };

            // Update version map incrementally - O(1)
            const versionMap = new Map([[data.version_number, 0]]);
            versionIndexMaps.current.set(messageId, versionMap);
          }
        })
      );

      // Reset buffer and counter
      // chunkBufferRef.current[messageId] = '';
      // chunkCounterRef.current[messageId] = 0;
      // }
    } else if (data.type === 'canvas-preview') {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );
        updatedMessages[messageIndex].canvas_preview = {
          message_id: data.message_id,
          content: data.content,
        };
        return updatedMessages;
      });
    } else if (data.type === 'research') {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );

        // Initialize research array if it doesn't exist

        if (messageIndex === -1) {
          updatedMessages[messageIndex] = {
            ...updatedMessages[messageIndex],
            research: [{ id: data.id, agent_name: data.agent_name, title: data.title }],
          };
        } else {
          const researchExists = updatedMessages[messageIndex].research?.some(
            (r) => r.id === data.id
          );
          if (!researchExists) {
            updatedMessages[messageIndex].research = [
              ...(updatedMessages[messageIndex].research || []),
              { id: data.id, agent_name: data.agent_name, title: data.title },
            ];
          }
        }
        return updatedMessages;
      });
    } else if (data.type === 'research-chunk') {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );

        if (messageIndex !== -1) {
          if (!updatedMessages[messageIndex].research) {
            updatedMessages[messageIndex].research = [];
          }

          const researchList = updatedMessages[messageIndex].research;
          const existingIndex = researchList.findIndex((r) => r.id === data.id);

          if (existingIndex !== -1) {
            const existingResearch = researchList[existingIndex];

            const newChunk = data.title || '';
            const currentTitle = existingResearch.title || '';

            // Only append new data if it's not already there
            //TODO: Check if the new chunk is already part of the current title might need some work on future
            if (!currentTitle.endsWith(newChunk)) {
              existingResearch.title = currentTitle + newChunk.replace(currentTitle, '');
            }
          } else {
            researchList.push({
              id: data.id,
              agent_name: data.agent_name || '',
              title: data.title || '',
            });
          }
        }

        return updatedMessages;
      });
    } else if (data.type === 'progress') {
      setMessages((prevMessages) => {
        // Create a new array to avoid direct mutation
        const updatedMessages = [...prevMessages];
        // Find the index of the message to update
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );

        // If the message is found, update its progress
        if (messageIndex !== -1) {
          updatedMessages[messageIndex] = {
            ...updatedMessages[messageIndex],
            progress: data.progress_bar, // Set the progress value from the API event
            // The agent name is set when the query starts, so we don't need to set it here
            // unless the API event also provides it.
          };
        }
        // Return the new, updated array of messages
        return updatedMessages;
      });
    } else if (data.type === 'related_queries') {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );
        if (messageIndex !== -1) {
          updatedMessages[messageIndex] = {
            ...updatedMessages[messageIndex],
            related_queries: data.content,
          };
        }
        return updatedMessages;
      });
    } else if (data.type === 'sources') {
      console.log('sources', data.content);
      // setMessages((prevMessages) => {
      //   const updatedMessages = [...prevMessages];
      //   const messageIndex = updatedMessages.findIndex(
      //     (element) => element.message_id === data.message_id
      //   );

      //   updatedMessages[messageIndex] = {
      //     ...updatedMessages[messageIndex],
      //     sources: data.content,
      //   };
      //   return updatedMessages;
      // });

      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );
        if (messageIndex === -1) return updatedMessages;
        const raw = data.content;
        let parsed = raw;
        if (typeof raw === 'string') {
          try {
            parsed = JSON.parse(raw);
          } catch {
            parsed = [];
          }
        }
        updatedMessages[messageIndex] = {
          ...updatedMessages[messageIndex],
          sources: Array.isArray(parsed) ? parsed : [],
        };
        return updatedMessages;
      });
    } else if (data.type === 'response_time') {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );

        updatedMessages[messageIndex] = {
          ...updatedMessages[messageIndex],
          response_time: data.content,
        };
        return updatedMessages;
      });
    } else if (data.type === 'complete') {
      setIsProcessing(false);
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );

        updatedMessages[messageIndex] = {
          ...updatedMessages[messageIndex],
          isSuggestion: data.suggestions,
          isRetry: data.retry,
          isElaborate: data.is_elaborate,
        };

        return updatedMessages;
      });
      setShowElaborateSummarize(data.suggestions ? true : false);
    } else if (data.type === 'complete' && data.notification === true) {
      sendNotification();
      if (eventSourceRef.current) {
        // console.log(eventSourceRef.current)
        eventSourceRef.current.close();
      }
    } else if (data.type === 'error') {
      setIsProcessing(false);
      setMessages((prev) => {
        const updatedMessages = [...prev];

        const currentMessageIndex = updatedMessages.findIndex(
          (message) => message.message_id === data.message_id
        );

        updatedMessages[currentMessageIndex] = {
          ...updatedMessages[currentMessageIndex],
          error: true,
        };
        return updatedMessages;
      });
      if (eventSourceRef.current) {
        // console.log(eventSourceRef.current)
        eventSourceRef.current.close();
      }
    } else if (data.type === 'context') {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(
          (element) => element.message_id === data.message_id
        );

        updatedMessages[messageIndex] = {
          ...updatedMessages[messageIndex],
          heading: data.Contextual_response,
        };
        return updatedMessages;
      });
    }
  }

  // On component mount, check for session and initialize

  useEffect(() => {
    const sessionIdFromParams = searchParams.get('search');
    if (chatDivRef.current) {
    }
    const response = {
      data: {
        data: [
          {
            timeline: 'Today',
            data: [
              {
                title: initialMessageData ?? '',
                id: sessionIdFromParams ?? '',
                created_at: formatDateWithMicroseconds(new Date()),
              },
            ],
          },
        ],
      },
    };
    if (initialMessageData && sessionIdFromParams) {
      setSessionHistoryData((prev) => {
        return handlePaginationData(response, prev, ADD_FORM.TOP);
      });
    }

    // Skip the full reload logic if we're just replacing the URL
    if (isReplacingRef.current) {
      isReplacingRef.current = false; // Reset for next time
      return;
    }

    if (initialMessageData) {
      setIsProcessing(true);
      startEventStream(initialMessageData);
      return;
    }

    // Check if sessionIdFromParams is valid
    if (sessionIdFromParams && sessionIdFromParams.length === 36) {
      setSessionId(sessionIdFromParams);
      getMessages(sessionIdFromParams);
    } else {
      router.push('/');
      toast.error(`Unable to load conversation ${query}`);
    }
  }, [searchParams]);

  useEffect(() => {
    messages.forEach((message) => {
      const chartArray = Array.isArray(message.chart_data) ? message.chart_data : [];

      chartArray.forEach((chart, index) => {
        const symbol = chart?.realtime?.symbol ?? '';
        if (!symbol) return;
        const key = `${message.message_id}-${symbol}`;

        // Open the very first chart by default
        if (
          !hasSetDefaultChartRef.current &&
          messages.length > 0 &&
          messages[0].message_id === message.message_id &&
          index === 0
        ) {
          setOpenSpecificChart([key]);
          hasSetDefaultChartRef.current = true;
        }

        // Reliably update the chart data state without causing extra re-renders
        setChartDataByMessage((currentChartData) => {
          if (!currentChartData[key]) {
            return { ...currentChartData, [key]: [chart] };
          }
          return currentChartData;
        });
      });
    });
  }, [messages, setChartDataByMessage]);

  useEffect(() => {
    // Clear the processing ID when processing finishes
    if (!isProcessing) {
      setProcessingMessageId(null);
    }
  }, [isProcessing]);

  // This hook handles all scrolling logic
  useEffect(() => {
    // Prevents scrolling on the initial page load
    if (initialRef.current) {
      initialRef.current = false;
      return;
    }

    // If a specific message is processing, scroll to it
    if (processingMessageId && isProcessing) {
      const element = messageRefs.current.get(processingMessageId);

      if (element) {
        // Use a timeout to ensure the DOM is updated before scrolling
        const timer = setTimeout(() => {
          element.scrollIntoView({
            behavior: 'smooth',
            block: 'start', // Brings the top of the element into view
          });
        }, 100);

        return () => clearTimeout(timer);
      }
    }
  }, [processingMessageId, isProcessing]);

  useLayoutEffect(() => {
    const chatDiv = chatDivRef.current;
    // This logic is only needed on mobile to counteract the padding shift.
    if (!isMobile || !chatDiv) {
      return;
    }

    if (isProcessing) {
      // While processing, we store the current scroll position as the "anchor".
      // This happens on every render, so it's always up-to-date.
      scrollAnchorRef.current = {
        scrollTop: chatDiv.scrollTop,
        scrollHeight: chatDiv.scrollHeight,
      };
    } else if (scrollAnchorRef.current) {
      // Processing just finished. A layout shift from padding removal has occurred.
      // We restore the scroll position based on the last known anchor.
      const { scrollTop, scrollHeight } = scrollAnchorRef.current;
      chatDiv.scrollTop = scrollTop + (chatDiv.scrollHeight - scrollHeight);

      // Clear the anchor until the next processing cycle.
      scrollAnchorRef.current = null;
    }
    // This effect runs when processing state changes or when new messages update the view.
  }, [isProcessing, isMobile, messages]);

  const startEventStream = async (
    userQuery = query,
    messageId = '',
    retry = false,
    isFirstQuery = true,
    agentValue: string = currentSearchMode,
    isElaborate = false,
    isWithExample = false
  ) => {
    const access_token = Cookies.get('access_token');

    if (!access_token) {
      logout();
      return;
    }

    // Cleanup previous connection
    if (abortControllerRef.current) {
      const controller = abortControllerRef.current;
      controller.abort();
      abortControllerRef.current = null;
    }

    // Create new abort controller
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Timeout management
    let timeoutId: NodeJS.Timeout | undefined;
    const STREAM_TIMEOUT = 10000; // 10 seconds for chat responses

    const resetTimeout = () => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        console.warn('⏰ Stream timeout - no data received for 10 seconds');
        controller.abort();
        handleStreamTimeout();
      }, STREAM_TIMEOUT);
    };

    const handleStreamTimeout = () => {
      setIsProcessing(false);
      toast.warning('Response is taking longer than expected. Please try again.');

      // Update the message state to show timeout
      setMessages((prev) => {
        const updated = [...prev];

        if (messageId === '') {
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            error: true,
          };
          return updated;
        }
        const messageIndex = updated.findIndex((m) => m.message_id === messageId);

        console.log(messageIndex, 'messageIndex');
        if (messageIndex !== -1) {
          updated[messageIndex] = {
            ...updated[messageIndex],
            error: true,
          };
        }
        return updated;
      });
    };

    const detectDisconnectionReason = (error: Error): string => {
      if (error.name === 'AbortError') {
        return 'cancelled';
      } else if (
        error.message.includes('fetch') ||
        error.message.includes('Failed to fetch') ||
        error.message.includes('network')
      ) {
        return 'network';
      } else if (
        error.message.includes('502') ||
        error.message.includes('503') ||
        error.message.includes('500')
      ) {
        return 'server_error';
      } else if (error.message.includes('timeout')) {
        return 'timeout';
      }
      return 'unknown';
    };

    const handleStreamError = (error: Error, context: string) => {
      const errorType = detectDisconnectionReason(error);
      console.log(`🔌 Stream disconnected during ${context}:`, {
        errorType,
        errorName: error.name,
        errorMessage: error.message,
        context,
      });

      setIsProcessing(false);

      // Show appropriate user message based on error type
      switch (errorType) {
        case 'cancelled':
          // Don't show error toast for manual cancellation
          console.log('🛑 Stream manually cancelled');
          break;
        case 'network':
          toast.error('Network connection lost. Please check your internet and try again.');
          break;
        case 'server_error':
          toast.error('Server temporarily unavailable. Please try again in a moment.');
          break;
        case 'timeout':
          toast.warning('Request timed out. Please try again.');
          break;
        default:
          toast.error('Connection error occurred. Please try again.');
      }

      // Update message state to show error
      setMessages((prev) => {
        const updated = [...prev];

        if (messageId === '' && errorType !== 'cancelled') {
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            error: true,
          };
          return updated;
        }

        const messageIndex = updated.findIndex((m) => m.message_id === messageId);
        if (messageIndex !== -1 && errorType !== 'cancelled') {
          updated[messageIndex] = {
            ...updated[messageIndex],
            error: true,
          };
        }
        return updated;
      });
    };

    let prevMessageId = '';
    if (retry) {
      const prevMessageIdx = messages.findIndex((message) => message.message_id === messageId) - 1;
      prevMessageId = prevMessageIdx !== -1 ? messages[prevMessageIdx].message_id : '';
    } else {
      prevMessageId = messages.length > 0 ? messages[messages.length - 1].message_id : '';
    }

    try {
      const fileDocuments = uploadedFileData.map((each) => ({
        fileName: each.fileName,
        fileType: each.type,
        generatedFileId: each.generatedFileId,
      }));
      const requestData = {
        session_id: sessionId,
        user_query: userQuery,
        realtime_info: true,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        search_mode: agentValue,
        message_id: messageId,
        retry: retry,
        prev_message_id: prevMessageId,
        doc_ids: fileDocuments.length > 0 ? fileDocuments : useMessageStore.getState().documents,
        is_elaborate: isElaborate,
        is_example: isWithExample,
      };

      console.log('🚀 Starting event stream...');

      const response = await fetch(API_ENDPOINTS.QUERY_STREAM, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          'Cache-Control': 'no-cache',
          Authorization: `Bearer ${access_token}`,
        },
        body: JSON.stringify(requestData),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
      }

      console.log('✅ Stream connection established');

      if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        // Start timeout monitoring
        resetTimeout();

        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              // Normal stream completion
              clearTimeout(timeoutId);
              console.log('✅ Stream completed successfully');
              setIsProcessing(false);
              break;
            }

            // Reset timeout on each chunk received (we're getting data)
            resetTimeout();

            // Process the chunk
            const chunk = decoder.decode(value, { stream: true });

            try {
              // Split by lines in case multiple events are in one chunk
              const lines = chunk.split('\n\n').filter((line) => line.trim());

              lines.forEach((line) => {
                try {
                  if (line.startsWith('data: ')) {
                    const eventData = line.substring(6);
                    const data = JSON.parse(eventData);
                    updateMessages(data);
                  } else if (line.startsWith('event: session_info')) {
                    // Handle session info - need to get the next line for data
                    const dataLine = line.split('\n')[1];
                    if (dataLine && dataLine.startsWith('data: ')) {
                      const sessionData = JSON.parse(dataLine.substring(6));
                      setMessageId(sessionData.message_id);
                      setProcessingMessageId(sessionData.message_id);
                      if (isFirstQuery) {
                        setQueryHeading(userQuery);
                        setSessionId(sessionData.session_id);
                        isReplacingRef.current = true;
                        router.replace(`/chat?search=${sessionData.session_id}`);
                      }

                      if (!retry) {
                        setMessages((prevMessages) => {
                          const newMsg: IMessage = {
                            message_id: sessionData.message_id,
                            query: userQuery,
                            files:
                              uploadedFileData.length > 0
                                ? uploadedFileData.map((file) => ({
                                  generatedFileId: file.generatedFileId,
                                  fileName: file.fileName,
                                  fileType: file.type,
                                }))
                                : useMessageStore.getState().documents || [],
                            progress: 0,
                            agent_name_for_progress: agentValue,
                          };
                          const updated = [...prevMessages, newMsg];
                          return updated;
                        });
                      }
                    }
                  } else if (line.startsWith('event: stock_chart')) {
                    // Handle stock chart events
                    const chartDataLine = line.split('\n')[1];
                    if (chartDataLine && chartDataLine.startsWith('data: ')) {
                      const chartData = JSON.parse(chartDataLine.substring(6));

                      try {
                        // Update the messages state with the new chart data
                        setMessages((prevMessages) => {
                          const updatedMessages = [...prevMessages];
                          const messageIndex = updatedMessages.findIndex(
                            (element) => element.message_id === chartData.message_id
                          );

                          if (messageIndex !== -1) {
                            if (
                              updatedMessages[messageIndex].chart_data &&
                              updatedMessages[messageIndex].chart_data.length > 0
                            ) {
                              updatedMessages[messageIndex] = {
                                ...updatedMessages[messageIndex],
                                chart_data: [
                                  ...updatedMessages[messageIndex].chart_data,
                                  {
                                    realtime: chartData.stock_data.realtime,
                                    historical: chartData.stock_data.historical,
                                    chart_session_id: chartData.stock_data.chart_session_id,
                                  },
                                ],
                              };
                            } else {
                              updatedMessages[messageIndex] = {
                                ...updatedMessages[messageIndex],
                                chart_data: [
                                  {
                                    realtime: chartData.stock_data.realtime,
                                    historical: chartData.stock_data.historical,
                                    chart_session_id: chartData.stock_data.chart_session_id,
                                  },
                                ],
                              };
                            }
                          }
                          return updatedMessages;
                        });
                      } catch (error) {
                        console.log('Error processing chart data:', error);
                      }
                    }
                  }
                } catch (lineError) {
                  console.warn('⚠️ Error parsing individual line (continuing):', lineError);
                  // Continue processing other lines even if one fails
                }
              });
            } catch (chunkError) {
              console.warn('⚠️ Error processing chunk (continuing):', chunkError);
              // Continue reading stream even if chunk processing fails
            }
          }
        } catch (readError: any) {
          clearTimeout(timeoutId);
          handleStreamError(readError, 'reading stream');
        } finally {
          // Ensure reader is released
          try {
            reader.releaseLock();
          } catch (e) {
            // Reader might already be released
          }
        }
      }
    } catch (fetchError: any) {
      if (timeoutId) clearTimeout(timeoutId);
      handleStreamError(fetchError, 'fetching');
    }
  };

  // Toggle expand for research items
  const toggleExpand = (messageId: string, index: number) => {
    // Find the message that contains the item being clicked
    const clickedMessage = messages.find((m) => m.message_id === messageId);

    // Check if it's the last item of the message currently being processed
    const isCurrentlyProcessingMessage = isProcessing && clickedMessage?.message_id === messageId;
    const isLastResearchItem =
      clickedMessage?.research && index === clickedMessage.research.length - 1;

    // If it is the last item being processed, do nothing on click
    if (isCurrentlyProcessingMessage && isLastResearchItem) {
      return;
    }

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
    const message = messages.find((m) => m.message_id === messageId);
    const hasResearch = message?.research && message.research.length > 0;
    setToggleResearchData((prev) => {
      if (prev.includes(messageId)) {
        return prev.filter((id) => id !== messageId);
      }
      if (hasResearch) {
        return [...prev, messageId];
      }
      return prev;
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
  const sendMessage = (relatedQuery = '') => {
    const messageToSend = relatedQuery || query.trim();
    setIsProcessing(true);
    setQueryHeading(messageToSend);
    setMessageId('');
    if (useMessageStore.getState().documents) {
      removeDocuments();
    }

    try {
      // Start generating the response
      startEventStream(messageToSend, '', false, false);
      setExpanded([]);
      setQuery('');

      setUploadedFileData([]);

      // Alternative: Scroll to the specific latest message element
      // You can use this instead of the above scrollTo method

      setTimeout(() => {
        if (textAreaRef.current) {
          textAreaRef.current.setSelectionRange(0, 0);
          textAreaRef.current.focus();
        }
      }, 0);
    } catch (error) {
      console.log('Error sending message:', error);
      setQuery('');
      setIsProcessing(false);
    }
  };

  const handleOpen = (idx: number) => {
    setOpen(true);
    setCurrentMessageIdx(idx);
  };

  const handleRewriteAnalysis = async (value: SearchMode, id: string, userQuery: string) => {
    setSearchMode(value);
    setProcessingMessageId(id);

    if (!id || id === '') {
      if (sessionId !== '') {
        return startEventStream(userQuery, id, false, false, value);
      } else {
        return startEventStream(userQuery, id, false, true, value);
      }
    }
    setMessageId(id);
    // const filteredMessage = messages[index];
    const updatedMessage = messages.map((message) => {
      if (message.message_id === id) {
        const {
          response,
          research,
          sources,
          related_queries,
          error,
          chart_data,
          map_data,
          feedback,
          response_time,
          isCancelled,
          isSuggestion,
          isElaborate,
          isRetry,
          ...rest
        } = message;
        // PROGRESS BAR INTEGRATION: Reset progress and set the new agent name on retry
        return {
          ...rest,
          progress: 0,
          agent_name_for_progress: value,
        };
      }
      return message;
    });
    setMessages(updatedMessage);
    try {
      setIsProcessing(true);
      startEventStream(userQuery, id, true, false, value);
      // startEventStream(sessionId);
    } catch (error) {
      console.log('Error sending message:', error);
    }
  };

  const handleFeedbackResponse = async (
    messageId: string,
    responseId: string,
    action: 'like' | 'dislike'
  ) => {
    const currentMessage = messages.find((msg) => msg.message_id === messageId);
    if (!currentMessage) return;

    const currentFeedback = currentMessage.feedback?.liked;

    let newFeedbackState: 'yes' | 'no' | null = null;
    // NOTE: This assumes your API can accept `null` to reset feedback.
    // If not, you may need to adjust the `apiPayload`.
    let apiPayload: boolean | null = null;

    if (action === 'like') {
      if (currentFeedback === 'yes') {
        // Already liked, so undo it
        newFeedbackState = null;
        apiPayload = null;
      } else {
        // Not liked (or disliked), so like it
        newFeedbackState = 'yes';
        apiPayload = true;
        toast.success('Thank you for your positive feedback!');
      }
    } else {
      // action === 'dislike'
      if (currentFeedback === 'no') {
        // Already disliked, so undo it
        newFeedbackState = null;
        apiPayload = null;
      } else {
        // Not disliked (or liked), so dislike it
        newFeedbackState = 'no';
        apiPayload = false;
        toast.info('Thank you for your feedback.');
      }
    }

    try {
      await axiosInstance.put('/response-feedback', {
        message_id: messageId,
        response_id: responseId,
        liked: apiPayload,
      });

      setMessages((prevMessages) =>
        prevMessages.map((message) => {
          if (message.message_id === messageId) {
            return {
              ...message,
              feedback: {
                ...message.feedback,
                liked: newFeedbackState,
              },
            };
          }
          return message;
        })
      );
    } catch (error) {
      console.log('Error sending feedback:', error);
      toast.error('Could not save your feedback. Please try again.');
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
      console.log('Download error:', error);
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
          console.log('❌ Notification error:', error);
        };

        console.log('✅ Notification created successfully');
      } else {
        console.log('❌ Permission not granted, cannot create notification');
      }
    } catch (error) {
      console.log('❌ Error in handleNotification:', error);
      toast.error('Error creating notification');
    }
  };

  const handleNotify = (e: React.MouseEvent) => {
    e.stopPropagation();
    console.log('🖱️ Button clicked - requesting notification');
    handleNotification();
  };

  const handleOpenFeedbackModal = (messageId: string, responseId: string) => {
    setReportMessageId(messageId);
    setReportResponseId(responseId);
    setOpenFeedbackModal(true);
    document.body.style.pointerEvents = 'auto';
  };

  const handleChatSharingModal = (messageId: string) => {
    setSharedMessageId(messageId);
    setOpenChatSharingModal(true);
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
  //           console.log('File not found in state', fileId);
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

  const stopGeneratingResponse = async () => {
    try {
      setIsStopGeneratingResponse(true);
      const response = await ApiServices.handleStopGeneratingResponse(sessionId, messageId);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
        setIsProcessing(false);
        setMessages((prev) => {
          const updatedMessages = [...prev];

          const currentMessageIdx = updatedMessages.findIndex(
            (message) => message.message_id === messageId
          );

          if (currentMessageIdx !== -1) {
            updatedMessages[currentMessageIdx] = {
              ...updatedMessages[currentMessageIdx],
              isCancelled: true,
            };
          }

          return updatedMessages;
        });
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to stop response generation');
    } finally {
      setIsStopGeneratingResponse(false);
    }
  };

  const handleElaborateResponse = (exampleStatus: string, messageId: string) => {
    setElaborateWithExample(exampleStatus);
    setShowElaborateSummarize(false);
    setIsProcessing(true);
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];

      const currentMessageIdx = updatedMessages.findIndex(
        (message) => message.message_id === messageId
      );

      if (currentMessageIdx !== -1) {
        updatedMessages[currentMessageIdx] = {
          ...updatedMessages[currentMessageIdx],
          isSuggestion: false,
          isElaborate: false,
        };
      }

      return updatedMessages;
    });
    const updatedQueryHeading = `Elaborate: ${queryHeading}`;
    const isExample = exampleStatus === 'with' ? true : false;

    setQueryHeading(updatedQueryHeading);
    startEventStream(updatedQueryHeading, '', false, false, 'summarizer', true, isExample);
  };

  const handleSummarizeResponse = (exampleStatus: string, messageId: string) => {
    setSummarizeWithExample(exampleStatus);
    setIsProcessing(true);
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];

      const currentMessageIdx = updatedMessages.findIndex(
        (message) => message.message_id === messageId
      );

      if (currentMessageIdx !== -1) {
        updatedMessages[currentMessageIdx] = {
          ...updatedMessages[currentMessageIdx],
          isSuggestion: false,
          isElaborate: false,
        };
      }

      return updatedMessages;
    });
    const isExample = exampleStatus === 'with' ? true : false;

    const updatedQueryHeading = `Summarize: ${queryHeading}`;
    setQueryHeading(updatedQueryHeading);
    startEventStream(updatedQueryHeading, '', false, false, 'summarizer', false, isExample);
  };

  const handleOpenCanvas = (idx: number) => {
    setCurrentCanvasMessageIdx(idx);
    setOpenCanvas(!openCanvas);
  };

  // Getting responsive classes based on the canvas open

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

  // Add this line right before your return statement
  const classes = getResponsiveClasses(openCanvas);

  return (
    <div className="w-full flex h-[calc(100vh-4.75rem)] lg:h-screen">
      {/* Add 'content-container' class to enable container queries */}
      <div
        data-detect={openCanvas ? 'canvas-open' : undefined}
        className={cn(
          'h-full pt-0 lg:pt-0 pb-4 lg:pb-6 lg:pr-8 flex flex-col bg-[var(--primary-main-bg)] transition-all duration-300',
          openCanvas ? 'lg:w-3/5' : 'w-full',
          openCanvas && 'content-container'
        )}
      >
        <Header heading={queryHeading} />

        <div className="lg:ml-8 lg:px-0 mt-2 w-full flex flex-col flex-grow overflow-hidden">
          <div
            ref={chatDivRef}
            className={cn(
              classes.chatContainer,
              // On desktop, use a consistent padding to prevent layout shifts.
              // On mobile, use a larger padding during processing to account for the fixed input bar.
              isMobile && isProcessing ? 'pb-[62dvh]' : 'pb-[100px]'
            )}
          >
            {messages.length > 0 &&
              messages.map((message, index) => {
                const isMessageProcessing =
                  isProcessing && message.message_id === processingMessageId;
                return (
                  <div
                    key={message.message_id}
                    ref={(element) => {
                      if (element) {
                        messageRefs.current.set(message.message_id, element);
                      } else {
                        messageRefs.current.delete(message.message_id);
                      }
                    }}
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
                      <div className="max-w-full rounded-xl border border-[#F3F0E8]">
                        <div
                          className={`bg-[var(--primary-main-bg)]" sm:px-4 px-2 sm:py-5 py-3 border border-[rgba(16,40,34,0.06)] ${!toggleResearchData.includes(message.message_id)
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
                              {/* PROGRESS BAR INTEGRATION: Conditionally render the progress bar for the 'agentic-planner' */}
                              {(message.agent_name_for_progress === 'agentic-planner' ||
                                message.agent_name_for_progress === 'agentic-reasoning' ||
                                message.agent_name_for_progress === 'deep-research') && (
                                  <div className="w-full">
                                    <Progress
                                      value={message.progress || 2}
                                      className="h-1.5 w-full bg-[rgba(75,151,112,0.1)] [&>div]:bg-[#4B9770]"
                                    />
                                  </div>
                                )}
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
                                  ease: [0.04, 0.62, 0.23, 0.98],
                                },
                                opacity: {
                                  duration: 0.25,
                                  ease: 'easeInOut',
                                },
                              }}
                              style={{ overflow: 'hidden' }}
                              className="w-full flex flex-col bg-[#F3F1EE] rounded-b-xl"
                            >
                              <div className="p-4 bg-[var(--primary-text-bg)]">
                                <div className="relative">
                                  {/* Timeline line */}
                                  <div className="absolute left-[0.9675rem] top-4 bottom-3 w-0.5 bg-[#4B9770]/10" />

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
                                                  isProcessing={isMessageProcessing}
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

                      {message.map_data && message.map_data.length > 0 && (
                        <div className={classes.mobileMap}>
                          <MapView hexagonData={message.map_data} />
                        </div>
                      )}

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
                                    isProcessing={isMessageProcessing}
                                  >
                                    {content}
                                  </Markdown>
                                </div>
                              );
                            })()}

                            {message.response && (
                              <div className="my-6 flex flex-1 flex-col self-stretch justify-end items-start gap-6">
                                {/* Suggestion Box (Elaborate/Summarize) */}
                                {message.isSuggestion && (
                                  <div className="flex flex-col self-stretch items-start justify-center gap-2 rounded-xl py-3">
                                    {/* Container for the buttons */}
                                    <div className="flex items-center gap-4">
                                      {/* Elaborate Button */}
                                      {message.isElaborate ? (
                                        <DropdownMenu>
                                          <DropdownMenuTrigger className="flex items-center gap-1 rounded-lg py-2">
                                            <Image
                                              src={'/icons/list_plus_icon.svg'}
                                              alt="icon"
                                              height="20"
                                              width="20"
                                            />
                                            <span className="text-base font-medium leading-normal text-[#4B9770]">
                                              Elaborate
                                            </span>
                                            <Image
                                              src={'/icons/arrow_button_icon.svg'}
                                              alt="icon"
                                              width="12"
                                              height="7"
                                              className="flex-shrink-0"
                                            />
                                          </DropdownMenuTrigger>
                                          <DropdownMenuContent className="ml-2">
                                            <DropdownMenuRadioGroup
                                              value={elaborateWithExample}
                                              onValueChange={(value) =>
                                                handleElaborateResponse(value, message.message_id)
                                              }
                                            >
                                              <DropdownMenuRadioItem value="with">
                                                With Example
                                              </DropdownMenuRadioItem>
                                              <DropdownMenuRadioItem value="without">
                                                Without Example
                                              </DropdownMenuRadioItem>
                                            </DropdownMenuRadioGroup>
                                          </DropdownMenuContent>
                                        </DropdownMenu>
                                      ) : (
                                        <DropdownMenu>
                                          <DropdownMenuTrigger className="flex items-center gap-1 rounded-lg py-2">
                                            <Image
                                              src={'/icons/summarize_icon.svg'}
                                              alt="icon"
                                              height="20"
                                              width="20"
                                            />
                                            <span className="text-base font-medium leading-normal text-[#4B9770]">
                                              Summarize
                                            </span>
                                            <Image
                                              src={'/icons/arrow_button_icon.svg'}
                                              alt="icon"
                                              width="12"
                                              height="7"
                                              className="flex-shrink-0"
                                            />
                                          </DropdownMenuTrigger>
                                          <DropdownMenuContent className="ml-2">
                                            <DropdownMenuRadioGroup
                                              value={summarizeWithExample}
                                              onValueChange={(value) =>
                                                handleSummarizeResponse(value, message.message_id)
                                              }
                                            >
                                              <DropdownMenuRadioItem value="with">
                                                With Example
                                              </DropdownMenuRadioItem>
                                              <DropdownMenuRadioItem value="without">
                                                Without Example
                                              </DropdownMenuRadioItem>
                                            </DropdownMenuRadioGroup>
                                          </DropdownMenuContent>
                                        </DropdownMenu>
                                      )}
                                    </div>
                                  </div>
                                )}
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
                                          {message.isRetry && (
                                            <DropdownMenu>
                                              <DropdownMenuTrigger className="focus:border-none focus:ring-0 outline-none">
                                                <TooltipProvider>
                                                  <Tooltip>
                                                    <TooltipTrigger asChild>
                                                      <Repeat
                                                        strokeWidth={1.5}
                                                        className="cursor-pointer size-[20px]"
                                                      />
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                      <p>Retry</p>
                                                    </TooltipContent>
                                                  </Tooltip>
                                                </TooltipProvider>
                                              </DropdownMenuTrigger>

                                              <DropdownMenuContent
                                                className="
    ml-5 w-64 flex flex-col items-start p-3 gap-[10px] 
  rounded-xl bg-[var(--primary-main-bg)] border-none 
  shadow-[0_7px_30px_0_rgba(0,0,0,0.06)]
  "
                                              >
                                                <DropdownMenuLabel className="px-1 py-0 text-xs font-medium not-italic leading-normal text-[#373737]">
                                                  Try again with
                                                </DropdownMenuLabel>

                                                <hr className="w-[226px] h-px bg-[#E9E5D2] border-0" />

                                                <DropdownMenuRadioGroup
                                                  value={currentSearchMode}
                                                  onValueChange={(value) => {
                                                    handleRewriteAnalysis(
                                                      value as SearchMode,
                                                      message.message_id,
                                                      message.query
                                                    );
                                                  }}
                                                  className="flex flex-col w-full gap-1"
                                                >
                                                  {retryOptions.map((option) => (
                                                    <DropdownMenuRadioItem
                                                      key={option.value}
                                                      value={option.value}
                                                      className="
group flex flex-col justify-center items-start self-stretch
px-3 py-2 rounded-xl cursor-pointer
border-none outline-none select-none
focus:bg-[var(--primary-chart-bg)]
data-[state=checked]:bg-[rgba(127,178,157,0.16)]
[&>span:first-child]:hidden
"
                                                    >
                                                      <span
                                                        className="
            font-medium text-sm text-black
            group-data-[state=checked]:text-[#4B9770]
          "
                                                      >
                                                        {option.title}
                                                      </span>
                                                      <span
                                                        className="
  text-[10px] not-italic font-normal leading-normal text-[#676767]
  group-data-[state=checked]:font-medium
  group-data-[state=checked]:text-black
"
                                                      >
                                                        {option.description}
                                                      </span>
                                                    </DropdownMenuRadioItem>
                                                  ))}
                                                </DropdownMenuRadioGroup>
                                              </DropdownMenuContent>
                                            </DropdownMenu>
                                          )}

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

                                          <TooltipProvider>
                                            <Tooltip>
                                              <TooltipTrigger asChild>
                                                <Share2
                                                  onClick={() =>
                                                    handleChatSharingModal(message.message_id)
                                                  }
                                                  strokeWidth={1.5}
                                                  className="cursor-pointer size-[20px]"
                                                />
                                              </TooltipTrigger>
                                              <TooltipContent>
                                                <p>Share</p>
                                              </TooltipContent>
                                            </Tooltip>
                                          </TooltipProvider>

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
                                          {message.isRetry && (
                                            <DropdownMenu>
                                              <DropdownMenuTrigger className="focus:border-none focus:ring-0 outline-none">
                                                <TooltipProvider>
                                                  <Tooltip>
                                                    <TooltipTrigger asChild>
                                                      <Repeat
                                                        strokeWidth={1.5}
                                                        className="cursor-pointer size-[20px]"
                                                      />
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                      <p>Retry</p>
                                                    </TooltipContent>
                                                  </Tooltip>
                                                </TooltipProvider>
                                              </DropdownMenuTrigger>

                                              <DropdownMenuContent
                                                className="
    ml-5 w-64 flex flex-col items-start p-3 gap-[10px] 
  rounded-xl bg-[var(--primary-main-bg)] border-none 
  shadow-[0_7px_30px_0_rgba(0,0,0,0.06)]
  "
                                              >
                                                <DropdownMenuLabel className="px-1 py-0 font-['Schibsted_Grotesk'] text-xs font-medium not-italic leading-normal text-[#373737]">
                                                  Try again with
                                                </DropdownMenuLabel>

                                                <hr className="w-[226px] h-px bg-[#E9E5D2] border-0" />

                                                <DropdownMenuRadioGroup
                                                  value={currentSearchMode}
                                                  onValueChange={(value) => {
                                                    handleRewriteAnalysis(
                                                      value as SearchMode,
                                                      message.message_id,
                                                      message.query
                                                    );
                                                  }}
                                                  className="flex flex-col w-full gap-1"
                                                >
                                                  {retryOptions.map((option) => (
                                                    <DropdownMenuRadioItem
                                                      key={option.value}
                                                      value={option.value}
                                                      className="
group flex flex-col justify-center items-start self-stretch
px-3 py-2 rounded-xl cursor-pointer
border-none outline-none select-none
focus:bg-[var(--primary-chart-bg)]
data-[state=checked]:bg-[rgba(127,178,157,0.16)]
[&>span:first-child]:hidden
"
                                                    >
                                                      {/* This is the simple, direct structure that will work */}
                                                      <span
                                                        className="
            font-medium text-sm text-black
            group-data-[state=checked]:text-[#4B9770]
          "
                                                      >
                                                        {option.title}
                                                      </span>
                                                      <span
                                                        className="
  text-[10px] not-italic font-normal leading-normal text-[#676767]
  group-data-[state=checked]:font-medium
  group-data-[state=checked]:text-black
"
                                                      >
                                                        {option.description}
                                                      </span>
                                                    </DropdownMenuRadioItem>
                                                  ))}
                                                </DropdownMenuRadioGroup>
                                              </DropdownMenuContent>
                                            </DropdownMenu>
                                          )}
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

                                          <TooltipProvider>
                                            <Tooltip>
                                              <TooltipTrigger asChild>
                                                <Share2
                                                  onClick={() =>
                                                    handleChatSharingModal(message.message_id)
                                                  }
                                                  strokeWidth={1.5}
                                                  className="cursor-pointer size-[20px]"
                                                />
                                              </TooltipTrigger>
                                              <TooltipContent>
                                                <p>Share</p>
                                              </TooltipContent>
                                            </Tooltip>
                                          </TooltipProvider>

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

                      {message.error && (
                        <div className="pt-6 py-4 ">
                          <div className="">
                            <div className="flex p-4 rounded-[1.25rem] bg-[#FFC4C24D] items-start text-[#AD2020] gap-x-2">
                              <PiWarningCircleFill className="size-6  flex-shrink-0" />
                              <div className="">
                                <h4 className="text-base font-medium">
                                  There was an error generating a response.
                                </h4>
                                <p className="text-xs font-normal">
                                  Due to an unexpected error, We couldn't complete your request.
                                  Please try again later{' '}
                                </p>
                              </div>
                            </div>

                            <div className="flex mt-6 items-center justify-center">
                              <button
                                onClick={() =>
                                  handleRewriteAnalysis(
                                    currentSearchMode,
                                    message.message_id || '',
                                    message.query
                                  )
                                }
                                className="py-2.5 px-[1.25rem] text-primary-main border border-primary-main rounded-lg flex items-center justify-center gap-x-2 text-sm font-medium leading-normal tracking-normal"
                              >
                                <BsArrowRepeat className="size-5 -rotate-45" />
                                Regenerate Response
                              </button>
                            </div>
                          </div>
                        </div>
                      )}

                      {message.related_queries && (
                        <div key={index} className="mt-6 mb-4">
                          <h2 className="sm:text-lg text-base font-semibold mb-4 text-black">
                            Related Queries
                          </h2>
                          <div className="space-y-3">
                            {message.related_queries?.map((query: string, index) => (
                              <div
                                key={index}
                                onClick={() => {
                                  sendMessage(query);
                                }}
                                className="flex justify-between items-center self-stretch bg-[var(--primary-main-bg)] cursor-pointer py-4 px-3 border-b border-[rgba(16,40,34,0.04)] text-[#54635F] text-sm font-normal leading-6 not-italic"
                              >
                                <p className="font-schibsted text-[#2E2E2E] sm:text-sm text-xs font-normal leading-relaxed">
                                  {query}
                                </p>
                                <button>
                                  <Image
                                    src="/icons/arrow_relatedquery_icon.svg"
                                    alt="relatedquery icon"
                                    priority
                                    height={20}
                                    width={20}
                                    className="w-[20px] h-[20px] text-[#2E2E2E]"
                                  />
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
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

                      {message.map_data && message.map_data.length > 0 && (
                        <div className={classes.mobileMap}>
                          <MapView hexagonData={message.map_data} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
          </div>

          <div className={classes.inputContainer}>
            <div className={classes.inputColumn}>
              <div className="flex flex-col items-start sm:p-4 p-3 rounded-[1rem] border-2 focus-within:border-transparent focus-within:bg-[var(--primary-chart-bg)] transition overflow-hidden">
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
                    {isProcessing ? (
                      <button
                        disabled={isStopGeneratingResponse}
                        onClick={stopGeneratingResponse}
                        className="flex items-center justify-center size-10 disabled:bg-primary-200 rounded-full bg-[#4B9770]"
                      >
                        {isStopGeneratingResponse ? (
                          <Loader2 className="size-4 text-white animate-spin" />
                        ) : (
                          <div className="size-3.5 bg-white rounded"></div>
                        )}
                      </button>
                    ) : (
                      <>
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
                      </>
                     
                    )}
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
      <ChatSharingDialog
        open={openChatSharingModal}
        onOpenChange={setOpenChatSharingModal}
        sessionId={sessionId}
        type="message"
        messageId={sharedMessageId}
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
      {showExitConsent && (
        <WaitUntilResponse open={showExitConsent} onOpenChange={setShowExitConsent} />
      )}
    </div>
  );
};

export default SpecificChat;
