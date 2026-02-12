import type { AvatarMode } from "./avatar-state-machine";

interface AvatarCharacterProps {
  mode: AvatarMode;
}

export const AvatarCharacter: React.FC<AvatarCharacterProps> = ({ mode }) => {
  if (mode === "hidden") return null;

  const eyesClosed = mode === "dozing";
  const isExcited = mode === "wake-up" || mode === "stretch";

  return (
    <div className={`avatar-container avatar-mode-${mode}`}>
      <div className="avatar-character">
        <div className="avatar-body">
          {/* Cheeks - subtle blush */}
          <div className="avatar-cheek left" />
          <div className="avatar-cheek right" />

          <div className="avatar-face">
            <div className="avatar-eyes">
              <div
                className={`avatar-eye left${eyesClosed ? " closed" : ""}${isExcited ? " excited" : ""}`}
              />
              <div
                className={`avatar-eye right${eyesClosed ? " closed" : ""}${isExcited ? " excited" : ""}`}
              />
            </div>
            <div className={`avatar-mouth ${mode}`} />
          </div>

          {/* Arms for stretch mode */}
          {mode === "stretch" && (
            <>
              <div className="avatar-arm left" />
              <div className="avatar-arm right" />
            </>
          )}
        </div>

        {/* ZZZ floating effect for dozing */}
        {mode === "dozing" && (
          <div className="avatar-zzz">
            <span className="z z1">z</span>
            <span className="z z2">z</span>
            <span className="z z3">Z</span>
          </div>
        )}
      </div>
    </div>
  );
};
