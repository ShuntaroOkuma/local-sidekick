import React, { useEffect, useState } from "react";
import "./speech-bubble.css";

interface SpeechBubbleProps {
  message: string | null;
  visible: boolean;
}

export const SpeechBubble: React.FC<SpeechBubbleProps> = ({
  message,
  visible,
}) => {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (visible && message) {
      setShow(true);
    } else {
      setShow(false);
    }
  }, [visible, message]);

  if (!message && !show) return null;

  return (
    <div
      className={`speech-bubble ${show ? "speech-bubble-enter" : "speech-bubble-exit"}`}
    >
      <div className="speech-bubble-content">{message}</div>
      <div className="speech-bubble-tail" />
    </div>
  );
};
