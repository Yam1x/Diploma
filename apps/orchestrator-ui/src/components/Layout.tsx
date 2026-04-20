import { PropsWithChildren, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { NotificationItem } from "../api/client";
import { NotificationsProvider, useNotifications } from "./NotificationsProvider";

function isBackupSettingsRoute(pathname: string) {
  return pathname === "/" || (pathname.startsWith("/tasks/") && !pathname.startsWith("/tasks/new"));
}

function isEventRulesRoute(pathname: string) {
  return pathname.startsWith("/event-rules");
}

function formatNotificationDate(value: string) {
  return new Date(value).toLocaleString();
}

function getSeverityIcon(severity: NotificationItem["severity"]) {
  const icons: Record<NotificationItem["severity"], string> = {
    info: "i",
    success: "+",
    warning: "!",
    error: "x",
  };

  return icons[severity];
}

export function Layout({ children }: PropsWithChildren) {
  return (
    <NotificationsProvider>
      <LayoutContent>{children}</LayoutContent>
    </NotificationsProvider>
  );
}

function LayoutContent({ children }: PropsWithChildren) {
  const location = useLocation();
  const { unreadCount, items, loading, error, refreshNotifications, markAllNotificationsRead, markNotificationRead } =
    useNotifications();
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  useEffect(() => {
    setNotificationsOpen(false);
  }, [location.pathname]);

  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Diploma Control Plane</p>
          <h1>РћСЂРєРµСЃС‚СЂР°С†РёСЏ СЂРµР·РµСЂРІРЅРѕРіРѕ РєРѕРїРёСЂРѕРІР°РЅРёСЏ РґР»СЏ Kubernetes</h1>
          <p className="subtle">
            РќР°СЃС‚СЂР°РёРІР°Р№С‚Рµ backup-СЃРµСЂРІРёСЃС‹ Рё РїСЂРѕСЃРјР°С‚СЂРёРІР°Р№С‚Рµ Р°СЂС‚РµС„Р°РєС‚С‹ РІ MinIO РёР· РѕРґРЅРѕР№ РїР°РЅРµР»Рё СѓРїСЂР°РІР»РµРЅРёСЏ.
          </p>
        </div>
        <div className="notification-shell">
          <button
            type="button"
            className="notification-button"
            aria-label="РЈРІРµРґРѕРјР»РµРЅРёСЏ"
            aria-expanded={notificationsOpen}
            onClick={() =>
              setNotificationsOpen((current) => {
                if (!current) {
                  void refreshNotifications();
                }

                return !current;
              })
            }
          >
            <span className="notification-bell" aria-hidden="true">
              рџ””
            </span>
            {unreadCount > 0 ? <span className="notification-badge">{unreadCount}</span> : null}
          </button>
          {notificationsOpen ? (
            <section className="notification-panel card" aria-label="РЎРїРёСЃРѕРє СѓРІРµРґРѕРјР»РµРЅРёР№">
              <div className="notification-panel-header">
                <div>
                  <p className="eyebrow">Notifications</p>
                  <h3>РЈРІРµРґРѕРјР»РµРЅРёСЏ</h3>
                </div>
                <button type="button" className="button ghost" onClick={() => void markAllNotificationsRead()}>
                  РџСЂРѕС‡РёС‚Р°С‚СЊ РІСЃРµ
                </button>
              </div>
              {error ? <div className="alert">{error}</div> : null}
              <div className="notification-list">
                {loading && items.length === 0 ? <p className="subtle">Р—Р°РіСЂСѓР·РєР° СѓРІРµРґРѕРјР»РµРЅРёР№...</p> : null}
                {!loading && items.length === 0 ? <p className="subtle">РџРѕРєР° РЅРµС‚ СѓРІРµРґРѕРјР»РµРЅРёР№.</p> : null}
                {items.map((item) =>
                  item.linkPath ? (
                    <Link
                      key={item.id}
                      className={`notification-item severity-${item.severity}${item.isRead ? " is-read" : ""}`}
                      to={item.linkPath}
                      onClick={() => {
                        void markNotificationRead(item.id);
                      }}
                    >
                      <span className="notification-icon" aria-hidden="true">
                        {getSeverityIcon(item.severity)}
                      </span>
                      <span className="notification-copy">
                        <strong>{item.title}</strong>
                        <span>{item.message}</span>
                        <time dateTime={item.createdAt}>{formatNotificationDate(item.createdAt)}</time>
                      </span>
                    </Link>
                  ) : (
                    <button
                      key={item.id}
                      type="button"
                      className={`notification-item severity-${item.severity}${item.isRead ? " is-read" : ""}`}
                      onClick={() => void markNotificationRead(item.id)}
                    >
                      <span className="notification-icon" aria-hidden="true">
                        {getSeverityIcon(item.severity)}
                      </span>
                      <span className="notification-copy">
                        <strong>{item.title}</strong>
                        <span>{item.message}</span>
                        <time dateTime={item.createdAt}>{formatNotificationDate(item.createdAt)}</time>
                      </span>
                    </button>
                  ),
                )}
              </div>
            </section>
          ) : null}
        </div>
      </header>
      <div className="workspace">
        <aside className="sidebar card">
          <div className="sidebar-group">
            <p className="sidebar-title">РЎРµСЂРІРёСЃС‹ Р±СЌРєР°РїРёСЂРѕРІР°РЅРёСЏ</p>
            <nav className="sidebar-nav">
              <Link className={isBackupSettingsRoute(location.pathname) ? "sidebar-link active" : "sidebar-link"} to="/">
                РќР°СЃС‚СЂРѕР№РєР° СЃРµСЂРІРёСЃРѕРІ
              </Link>
              <Link className={isEventRulesRoute(location.pathname) ? "sidebar-link active" : "sidebar-link"} to="/event-rules">
                Combined Event Rules
              </Link>
              <Link className={location.pathname.startsWith("/tasks/new") ? "sidebar-link active" : "sidebar-link"} to="/tasks/new">
                РќРѕРІР°СЏ Р·Р°РґР°С‡Р°
              </Link>
            </nav>
          </div>
          <div className="sidebar-group">
            <p className="sidebar-title">РҐСЂР°РЅРёР»РёС‰Рµ</p>
            <nav className="sidebar-nav">
              <Link className={location.pathname.startsWith("/minio-files") ? "sidebar-link active" : "sidebar-link"} to="/minio-files">
                РџСЂРѕСЃРјРѕС‚СЂ С„Р°Р№Р»РѕРІ РІ MinIO
              </Link>
            </nav>
          </div>
        </aside>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
