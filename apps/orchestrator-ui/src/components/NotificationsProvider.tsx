import { createContext, PropsWithChildren, useContext, useEffect, useEffectEvent, useState } from "react";

import { NotificationItem, NotificationsResponse, api } from "../api/client";

type NotificationsContextValue = {
  unreadCount: number;
  items: NotificationItem[];
  loading: boolean;
  error: string | null;
  refreshNotifications: () => Promise<void>;
  markNotificationRead: (notificationId: number) => Promise<void>;
  markAllNotificationsRead: () => Promise<void>;
};

const NotificationsContext = createContext<NotificationsContextValue>({
  unreadCount: 0,
  items: [],
  loading: false,
  error: null,
  refreshNotifications: async () => undefined,
  markNotificationRead: async () => undefined,
  markAllNotificationsRead: async () => undefined,
});

export function NotificationsProvider({ children }: PropsWithChildren) {
  const [notifications, setNotifications] = useState<NotificationsResponse>({ unreadCount: 0, items: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshNotifications = useEffectEvent(async () => {
    try {
      const response = await api.listNotifications();
      setNotifications(response);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить уведомления");
    } finally {
      setLoading(false);
    }
  });

  useEffect(() => {
    void refreshNotifications();
    const intervalId = window.setInterval(() => {
      void refreshNotifications();
    }, 30000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [refreshNotifications]);

  async function markNotificationRead(notificationId: number) {
    try {
      await api.markNotificationRead(notificationId);
      await refreshNotifications();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось обновить уведомление");
    }
  }

  async function markAllNotificationsRead() {
    try {
      await api.markAllNotificationsRead();
      await refreshNotifications();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось обновить уведомления");
    }
  }

  return (
    <NotificationsContext.Provider
      value={{
        unreadCount: notifications.unreadCount,
        items: notifications.items,
        loading,
        error,
        refreshNotifications,
        markNotificationRead,
        markAllNotificationsRead,
      }}
    >
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationsContext);
}
