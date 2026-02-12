import { AvatarCharacter } from "./AvatarCharacter";
import { useAvatarState } from "./useAvatarState";
import "./avatar.css";

export const AvatarApp: React.FC = () => {
  const { mode, notification } = useAvatarState();

  return (
    <div className="avatar-root">
      <AvatarCharacter mode={mode} />
      {notification && (
        <div className="avatar-notification">{notification.message}</div>
      )}
    </div>
  );
};
