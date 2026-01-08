// store/useMessageStore.ts
import { IPreviewFileData } from '@/app/(chats)/chat/component/SpecificChat';
import { IFinanceData } from '@/components/charts/FinanaceChart';
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export type SearchMode = 'fast' | 'agentic-planner' | 'agentic-reasoning';

type MessageState = {
  message: string | null;
  searchMode: SearchMode;
  documents: IPreviewFileData[] | [];
  financeChartModalData: IFinanceData[];
  setMessage: (message: string) => void;
  setSearchMode: (searchMode: SearchMode) => void;
  setDocuments: (documents: IPreviewFileData[]) => void;
  removeDocuments: () => void;
  resetSearchMode: () => void;
  setFinanceChartModalDataa: (financeChartModalData: IFinanceData[]) => void;
};

export const useMessageStore = create<MessageState>()(
  devtools(
    (set) => ({
      message: null,
      searchMode: 'fast',
      deepResearch: false,
      documents: [],
      setMessage: (message) => set({ message }, false, 'setMessage'),
      setSearchMode: (searchMode: SearchMode) => set({ searchMode }, false, 'setSearchMode'),
      setDocuments: (documents: IPreviewFileData[]) => set({ documents }, false, 'setDocuments'),
      removeDocuments: () => set({ documents: [] }, false, 'removeDocuments'),
      resetSearchMode: () => set({ searchMode: 'fast' }, false, 'resetSearchMode'),
      financeChartModalData: [],
      setFinanceChartModalDataa: (financeChartModalData: IFinanceData[]) =>
        set({ financeChartModalData }, false, 'financeChartModalData'),
    }),
    { name: 'MessageStore' }
  )
);

interface AuthState {
  username: string | null;
  email: string | null;
  isAuthenticated: boolean;
  profilePicture: string | null;
  setUser: (userName: string, email: string, profilePicture: string) => void;
  resetUser: () => void;
  setProfilePicture: (url: string) => void;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    (set) => ({
      username: null,
      email: null,
      isAuthenticated: false,
      profilePicture: null,
      setUser: (userName, email, profilePicture) =>
        set(
          {
            username: userName,
            email,
            isAuthenticated: true,
            profilePicture,
          },
          false,
          'setUser'
        ),
      resetUser: () =>
        set(
          {
            username: null,
            email: null,
            isAuthenticated: false,
            profilePicture: null,
          },
          false,
          'resetUser'
        ),
      setProfilePicture: (url: string) => set({ profilePicture: url }, false, 'setProfilePicture'),
    }),
    { name: 'AuthStore' }
  )
);
