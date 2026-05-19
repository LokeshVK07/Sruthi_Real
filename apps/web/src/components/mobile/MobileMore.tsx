import { ChevronRight, Clock3, Download, Heart, HelpCircle, ListMusic, Settings, Users } from "lucide-react";

type MobileMoreProps = {
  appName: string;
  favoriteCount: number;
  playlistCount: number;
  recentCount: number;
  onOpenFavorites: () => void;
  onOpenPlaylists: () => void;
  onOpenArtists: () => void;
  onOpenRecent: () => void;
  onOpenDownloaded: () => void;
  onOpenSettings: () => void;
  onOpenHelp: () => void;
};

export default function MobileMore({
  appName,
  favoriteCount,
  playlistCount,
  recentCount,
  onOpenFavorites,
  onOpenPlaylists,
  onOpenArtists,
  onOpenRecent,
  onOpenDownloaded,
  onOpenSettings,
  onOpenHelp,
}: MobileMoreProps) {
  const items = [
    { label: "Favorites", detail: `${favoriteCount} songs`, icon: Heart, onClick: onOpenFavorites },
    { label: "Playlists", detail: `${playlistCount} lists`, icon: ListMusic, onClick: onOpenPlaylists },
    { label: "Artists", detail: "Browse artists", icon: Users, onClick: onOpenArtists },
    { label: "Recently Played", detail: `${recentCount} songs`, icon: Clock3, onClick: onOpenRecent },
    { label: "Downloaded", detail: "Offline songs", icon: Download, onClick: onOpenDownloaded },
    { label: "Settings", detail: "App preferences", icon: Settings, onClick: onOpenSettings },
    { label: "Help & Support", detail: "Get help", icon: HelpCircle, onClick: onOpenHelp },
  ];

  return (
    <div className="mobile-screen mobile-more-screen">
      <div className="mobile-profile-card">
        <span className="mobile-profile-card__mark">V</span>
        <div>
          <strong>{appName}</strong>
          <span>Calm Tamil music, everywhere.</span>
        </div>
      </div>

      <div className="mobile-screen__header mobile-screen__header--compact">
        <div>
          <strong>More</strong>
          <span>Library and app shortcuts</span>
        </div>
      </div>

      <div className="mobile-more-list">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.label} type="button" className="mobile-more-row" onClick={item.onClick}>
              <span className="mobile-more-row__icon">
                <Icon size={18} />
              </span>
              <span className="mobile-more-row__copy">
                <strong>{item.label}</strong>
                <em>{item.detail}</em>
              </span>
              <ChevronRight size={17} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
