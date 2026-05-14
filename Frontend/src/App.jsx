import React, { useState, useRef, useEffect } from "react";
import "./index.css";
import { ExpertCouncilIcon } from "./ExpertCouncilIcon";

export default function App() {
  const [page, setPage] = useState("welcome");
  const [welcomeStep, setWelcomeStep] = useState("choose"); // "choose" | "experts"

  // Dynamic list of experts (defaults to 3, can add more)
  const [experts, setExperts] = useState(["Science", "Maths", "Biology"]);

  const [messages, setMessages] = useState([]);        // UI only
  const [llmHistory, setLlmHistory] = useState([]);    // LLM memory

  // BYOD chat state
  const [byodMessages, setByodMessages] = useState([]);
  const [byodHistory, setByodHistory] = useState([]);
  const [byodInput, setByodInput] = useState("");
  const [byodLoading, setByodLoading] = useState(false);
  const [byodUploading, setByodUploading] = useState(false);
  const [byodFile, setByodFile] = useState(null);
  const [byodDocName, setByodDocName] = useState("");
  const [byodTags, setByodTags] = useState("");
  const [byodDescription, setByodDescription] = useState("");
  const [byodUploadCollapsed, setByodUploadCollapsed] = useState(false);
  const [byodDragOver, setByodDragOver] = useState(false);
  const [byodUploadFeedback, setByodUploadFeedback] = useState(null); // { type: 'success'|'error', message }

  // Deep Reasoning chat state
  const [deepReasoningMessages, setDeepReasoningMessages] = useState([]);
  const [deepReasoningHistory, setDeepReasoningHistory] = useState([]);
  const [deepReasoningInput, setDeepReasoningInput] = useState("");
  const [deepReasoningLoading, setDeepReasoningLoading] = useState(false);

  // Vision (image) questions in expert chat
  const [visionFile, setVisionFile] = useState(null);
  const [visionUploading, setVisionUploading] = useState(false);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const messagesRef = useRef(null);
  const scrollAnchorRef = useRef(null);
  const currentTurnRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const silenceTimerRef = useRef(null);
  const lastChunkTimeRef = useRef(null);
  const byodFileInputRef = useRef(null);
  const visionFileInputRef = useRef(null);

  /* ---------------- navigation ---------------- */

  useEffect(() => {
    const handlePopState = () => {
      setPage("welcome");
      setWelcomeStep("choose");
      setMessages([]);
      setLlmHistory([]);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  /* ---------------- auto scroll ---------------- */

  useEffect(() => {
    if (scrollAnchorRef.current) {
      scrollAnchorRef.current.scrollIntoView({ behavior: "auto" });
    }
  }, [messages, byodMessages, deepReasoningMessages, page]);

  /* ---------------- send message ---------------- */

  async function sendMessage() {
    const trimmed = input.trim();

    // If an image is attached, route through the vision flow (text is optional).
    if (visionFile) {
      await sendVisionMessage();
      return;
    }

    // Text-only flow
    if (!trimmed) return;

    // stable ID for this turn
    currentTurnRef.current = Date.now();
    const turnId = currentTurnRef.current;

    /* ---- 1. UI update ---- */
    setMessages(prev => [
      ...prev,
      { role: "user", content: trimmed, justSent: true }
    ]);
    setInput("");
    setLoading(true);

    /* ---- 2. BUILD NEXT HISTORY EXPLICITLY (FIX) ---- */
    const nextHistory = [
      ...llmHistory,
      { role: "user", content: trimmed }
    ];

    setLlmHistory(nextHistory);

    const activeExperts = experts.filter(e => e && e !== "None");

    let assistantBuffer = "";

    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/ask/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          history: nextHistory,          // ✅ NOT stale
          experts: activeExperts
        })
      });

      if (!res.body) throw new Error("No stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let unlocked = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          let data;
          try {
            data = JSON.parse(line);
          } catch {
            console.warn("Bad JSON line from /ask/stream:", line);
            continue;
          }

          if (data.event === "end") continue;

          const rawExpert = (data.expert || "").trim();
          const expertLower = rawExpert.toLowerCase();
          const content = data.content ?? "";

          // Skip empty chunks and router-only messages on the UI
          if (!content) continue;
          if (expertLower === "router") continue;

          assistantBuffer += content;

          // unlock input once streaming begins
          if (!unlocked) {
            setLoading(false);
            unlocked = true;
          }

          /* ---- 3. UI streaming update ---- */
          setMessages(prev => {
            const copy = [...prev];

            // One assistant bubble per turn. We do NOT create separate bubbles
            // for "None" vs a later expert label; we just update the same one.
            let idx = copy.findIndex(
              m => m.role === "assistant" && m.turnId === turnId
            );

            if (idx === -1) {
              copy.push({
                role: "assistant",
                expert: undefined,
                turnId,
                content: ""
              });
              idx = copy.length - 1;
            }

            const current = copy[idx];

            // Prefer a real expert label when available, hide "none".
            const isRealExpert =
              rawExpert && expertLower !== "none";
            const nextExpert = isRealExpert
              ? rawExpert
              : current.expert;

            copy[idx] = {
              ...current,
              expert: nextExpert,
              content: (current.content || "") + content
            };

            return copy;
          });
        }
      }

      /* ---- 4. Commit assistant reply to LLM memory ---- */
      if (assistantBuffer.trim()) {
        setLlmHistory(prev => [
          ...prev,
          { role: "assistant", content: assistantBuffer }
        ]);
      }
    } catch (err) {
      console.error("Stream error:", err);
      setLoading(false);
    }
  }

  /* ---------------- vision (image) question in expert chat ---------------- */

  async function sendVisionMessage() {
    if (!visionFile) {
      alert("Please choose an image file containing text or content to analyze.");
      return;
    }

    const trimmedQuestion = input.trim();

    // stable ID for this turn
    currentTurnRef.current = Date.now();
    const turnId = currentTurnRef.current;

    // 1. UI: show a user bubble indicating an image question
    setMessages(prev => [
      ...prev,
      {
        role: "user",
        content: trimmedQuestion
          ? `📷 ${trimmedQuestion}`
          : "📷 Image question (analyzing…) ",
        justSent: true
      }
    ]);
    setInput("");
    setLoading(true);
    setVisionUploading(true);

    // 2. Extend LLM history with the textual part of the question (if any)
    const nextHistory = [...llmHistory];
    if (trimmedQuestion) {
      nextHistory.push({ role: "user", content: trimmedQuestion });
    }
    setLlmHistory(nextHistory);

    let assistantBuffer = "";

    const activeExperts = experts.filter(e => e && e !== "None");

    try {
      const formData = new FormData();
      formData.append("image", visionFile);
      formData.append(
        "meta",
        JSON.stringify({
          question: trimmedQuestion || null,
          history: nextHistory,
          experts: activeExperts,
          mode: "general"
        })
      );

      const res = await fetch(
        "http://127.0.0.1:8000/api/v1/ask/vision-query",
        {
          method: "POST",
          body: formData
        }
      );

      if (!res.body) throw new Error("No stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let unlocked = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;

          let data;
          try {
            data = JSON.parse(line);
          } catch {
            console.warn("Bad JSON line from /ask/vision-query:", line);
            continue;
          }

          // Special event: vision model summary of the image
          if (data.event === "vision_summary") {
            if (data.content) {
              setMessages(prev => [
                ...prev,
                {
                  role: "system",
                  expert: "Vision model",
                  content: `🖼️ ${data.content}`
                }
              ]);
            }
            continue;
          }

          if (data.event === "end") continue;

          const rawExpert = (data.expert || "").trim();
          const expertLower = rawExpert.toLowerCase();
          const content = data.content ?? "";

          if (!content) continue;
          if (expertLower === "router") continue;

          assistantBuffer += content;

          // unlock input once streaming begins
          if (!unlocked) {
            setLoading(false);
            setVisionUploading(false);
            unlocked = true;
          }

          // Stream assistant reply into a single bubble for this turn
          setMessages(prev => {
            const copy = [...prev];

            let idx = copy.findIndex(
              m => m.role === "assistant" && m.turnId === turnId
            );

            if (idx === -1) {
              copy.push({
                role: "assistant",
                expert: undefined,
                turnId,
                content: ""
              });
              idx = copy.length - 1;
            }

            const current = copy[idx];

            const isRealExpert =
              rawExpert && expertLower !== "none";
            const nextExpert = isRealExpert
              ? rawExpert
              : current.expert;

            copy[idx] = {
              ...current,
              expert: nextExpert,
              content: (current.content || "") + content
            };

            return copy;
          });
        }
      }

      if (assistantBuffer.trim()) {
        setLlmHistory(prev => [
          ...prev,
          { role: "assistant", content: assistantBuffer }
        ]);
      }
    } catch (err) {
      console.error("Vision stream error:", err);
      setMessages(prev => [
        ...prev,
        {
          role: "system",
          content:
            "There was a problem processing the image question. Please try again."
        }
      ]);
    } finally {
      setLoading(false);
      setVisionUploading(false);
      setVisionFile(null);
      if (visionFileInputRef.current) {
        visionFileInputRef.current.value = "";
      }
    }
  }

  /* ---------------- BYOD: upload + chat ---------------- */

  async function handleByodUpload(e) {
    e.preventDefault();
    if (!byodFile) {
      setByodUploadFeedback({ type: "error", message: "Please choose a file to upload." });
      return;
    }

    setByodUploadFeedback(null);
    setByodUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", byodFile);
      if (byodDocName.trim()) formData.append("doc_name", byodDocName.trim());
      if (byodTags.trim()) formData.append("tags", byodTags.trim());
      if (byodDescription.trim()) {
        formData.append("description", byodDescription.trim());
      }
      formData.append("source", "upload");
      formData.append("language", "en");

      const res = await fetch("http://127.0.0.1:8000/api/v1/ask/byod", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || "Failed to ingest document.");
      }

      let summaryText = "Document ingested successfully.";
      try {
        const data = await res.json();
        if (typeof data === "string") {
          summaryText = data;
        } else if (data && data.summary) {
          summaryText = data.summary;
        }
      } catch {
        // ignore JSON parse errors and keep default summary
      }

      setByodMessages(prev => [
        ...prev,
        {
          role: "system",
          content: `📄 ${summaryText}`
        }
      ]);
      setByodUploadFeedback({ type: "success", message: summaryText });
      setByodUploadCollapsed(true);
      setByodFile(null);
      setByodDocName("");
      setByodTags("");
      setByodDescription("");
      if (byodFileInputRef.current) byodFileInputRef.current.value = "";
    } catch (err) {
      console.error("BYOD upload error:", err);
      setByodUploadFeedback({
        type: "error",
        message: err.message || "Failed to ingest document. Please try again."
      });
    } finally {
      setByodUploading(false);
    }
  }

  function handleByodDrop(e) {
    e.preventDefault();
    setByodDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) setByodFile(file);
  }

  function handleByodDragOver(e) {
    e.preventDefault();
    setByodDragOver(true);
  }

  function handleByodDragLeave(e) {
    e.preventDefault();
    setByodDragOver(false);
  }

  async function sendByodMessage() {
    const trimmed = byodInput.trim();
    if (!trimmed) return;

    setByodMessages(prev => [
      ...prev,
      { role: "user", content: trimmed, justSent: true }
    ]);
    setByodInput("");
    setByodLoading(true);

    const nextHistory = [...byodHistory, { role: "user", content: trimmed }];
    setByodHistory(nextHistory);

    let assistantBuffer = "";

    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/ask/byod-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          history: nextHistory
        })
      });

      if (!res.body) throw new Error("No stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let unlocked = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;

          let data;
          try {
            data = JSON.parse(line);
          } catch {
            console.warn("Bad BYOD JSON line:", line);
            continue;
          }

          if (data.event === "end") continue;

          const content = data.content ?? "";
          if (!content) continue;

          assistantBuffer += content;

          if (!unlocked) {
            setByodLoading(false);
            unlocked = true;
          }

          setByodMessages(prev => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            if (last && last.role === "assistant") {
              copy[copy.length - 1] = {
                ...last,
                content: (last.content || "") + content
              };
            } else {
              copy.push({
                role: "assistant",
                content
              });
            }
            return copy;
          });
        }
      }

      if (assistantBuffer.trim()) {
        setByodHistory(prev => [
          ...prev,
          { role: "assistant", content: assistantBuffer }
        ]);
      }
    } catch (err) {
      console.error("BYOD stream error:", err);
      setByodLoading(false);
    }
  }

  /* ---------------- Deep Reasoning chat ---------------- */

  async function sendDeepReasoningMessage() {
    const trimmed = deepReasoningInput.trim();
    if (!trimmed) return;

    setDeepReasoningMessages(prev => [
      ...prev,
      { role: "user", content: trimmed, justSent: true }
    ]);
    setDeepReasoningInput("");
    setDeepReasoningLoading(true);

    const nextHistory = [...deepReasoningHistory, { role: "user", content: trimmed }];
    setDeepReasoningHistory(nextHistory);

    const turnId = Date.now();
    let finalAnswerBuffer = "";
    let hidePlanTimer = null;

    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/ask/deep-reasoning-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          history: nextHistory
        })
      });

      if (!res.body) throw new Error("No stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let unlocked = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;

          let data;
          try {
            data = JSON.parse(line);
          } catch {
            console.warn("Bad Deep Reasoning JSON line:", line);
            continue;
          }

          if (data.event === "end") continue;

          const content = data.content ?? "";
          const phase = (data.phase || "answer").toLowerCase();
          if (!content) continue;

          const isFinalPhase = phase === "final_answer";

          if (isFinalPhase) {
            finalAnswerBuffer += content;
          }

          if (!unlocked) {
            setDeepReasoningLoading(false);
            unlocked = true;
          }

          setDeepReasoningMessages(prev => {
            const copy = [...prev];
            let last = copy[copy.length - 1];
            if (last && last.role === "assistant") {
              if (isFinalPhase) {
                const next = {
                  ...last,
                  content: (last.content || "") + content,
                  turnId: last.turnId ?? turnId
                };
                if (next.hidePlanAt == null) {
                  next.hidePlanAt = Date.now() + 3000;
                  next.showPlan = true;
                  if (hidePlanTimer) clearTimeout(hidePlanTimer);
                  const idToHide = turnId;
                  hidePlanTimer = setTimeout(() => {
                    setDeepReasoningMessages(prev2 =>
                      prev2.map(m =>
                        m.role === "assistant" && m.turnId === idToHide && m.showPlan
                          ? { ...m, planFadingOut: true }
                          : m
                      )
                    );
                  }, 2500);
                }
                copy[copy.length - 1] = next;
              } else {
                copy[copy.length - 1] = {
                  ...last,
                  planContent: (last.planContent || "") + content,
                  content: last.content ?? "",
                  showPlan: true,
                  turnId: last.turnId ?? turnId
                };
              }
            } else {
              copy.push({
                role: "assistant",
                turnId,
                planContent: isFinalPhase ? "" : content,
                content: isFinalPhase ? content : "",
                showPlan: true,
                hidePlanAt: isFinalPhase ? Date.now() + 3000 : null
              });
              if (isFinalPhase) {
                if (hidePlanTimer) clearTimeout(hidePlanTimer);
                const idToHide = turnId;
                hidePlanTimer = setTimeout(() => {
                  setDeepReasoningMessages(prev2 =>
                    prev2.map(m =>
                      m.role === "assistant" && m.turnId === idToHide && m.showPlan
                        ? { ...m, planFadingOut: true }
                        : m
                    )
                  );
                }, 2500);
              }
            }
            return copy;
          });
        }
      }

      if (finalAnswerBuffer.trim()) {
        setDeepReasoningHistory(prev => [
          ...prev,
          { role: "assistant", content: finalAnswerBuffer }
        ]);
      }
    } catch (err) {
      console.error("Deep Reasoning stream error:", err);
      setDeepReasoningLoading(false);
    } finally {
      if (hidePlanTimer) clearTimeout(hidePlanTimer);
    }
  }

  /* ---------------- audio recording input ---------------- */

  async function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("Microphone access is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);

      audioChunksRef.current = [];
      lastChunkTimeRef.current = Date.now();

      mediaRecorder.ondataavailable = event => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
          lastChunkTimeRef.current = Date.now();
        }
      };

      mediaRecorder.onstop = async () => {
        if (silenceTimerRef.current) {
          clearInterval(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }

        stream.getTracks().forEach(track => track.stop());
        setIsRecording(false);

        if (!audioChunksRef.current.length) return;

        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm"
        });

        // show a user-side bubble so the voice query is visible in chat
        setMessages(prev => [
          ...prev,
          {
            role: "user",
            content: "🎧 Voice question (processing…) ",
            justSent: true
          }
        ]);

        // Placeholder: send audio to backend for further processing
        try {
          const formData = new FormData();
          formData.append("audio", audioBlob, "query.webm");
          formData.append(
            "meta",
            JSON.stringify({
              history: llmHistory,
              experts: experts.filter(e => e && e !== "None")
            })
          );

          const res = await fetch("http://127.0.0.1:8000/api/v1/ask/voice-query", {
            method: "POST",
            body: formData
          });
          
          if (!res.body) throw new Error("No response body");
          
          const reader = res.body.getReader();
          const decoder = new TextDecoder();

          let assistantMessage = "";
          
          while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });

            // Backend sends JSON per line
            const lines = chunk.split("\n").filter(Boolean);

            for (const line of lines) {
              try {
                const data = JSON.parse(line);

                if (data.event === "end") continue;

                // Backend sends transcript of the audio as:
                // { "event": "transcript", "content": "<user text>" }
                if (data.event === "transcript" && data.content) {
                  const transcript = data.content;

                  setMessages(prev => {
                    const copy = [...prev];
                    let idx = -1;

                    // Find the most recent user bubble (the placeholder voice bubble)
                    for (let i = copy.length - 1; i >= 0; i -= 1) {
                      if (copy[i].role === "user") {
                        idx = i;
                        break;
                      }
                    }

                    if (idx === -1) {
                      copy.push({
                        role: "user",
                        content: transcript,
                        justSent: true
                      });
                    } else {
                      copy[idx] = {
                        ...copy[idx],
                        content: transcript,
                        justSent: false
                      };
                    }

                    return copy;
                  });

                  // Do not treat transcript as assistant content
                  continue;
                }

                const expert = data.expert?.trim();

                if (data.content) {
                  assistantMessage += data.content;

                  // Update chat incrementally, keeping expert label
                  setMessages(prev => {
                    const copy = [...prev];

                    const last = copy[copy.length - 1];
                    if (last && last.role === "assistant" && last.expert === expert) {
                      copy[copy.length - 1] = {
                        ...last,
                        content: assistantMessage
                      };
                    } else {
                      copy.push({
                        role: "assistant",
                        expert,
                        content: assistantMessage
                      });
                    }

                    return copy;
                  });
                }
              } catch (e) {
                console.warn("Bad JSON chunk:", line);
              }
            }
          }
        } catch (err) {
          console.error("Audio upload error:", err);
          setMessages(prev => [
            ...prev,
            {
              role: "system",
              content:
                "Could not send audio to backend (placeholder endpoint error)."
            }
          ]);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      // collect chunks every 500ms so we can detect silence
      mediaRecorder.start(500);

      // watchdog: stop recording after a short period of silence
      if (silenceTimerRef.current) {
        clearInterval(silenceTimerRef.current);
      }
      silenceTimerRef.current = setInterval(() => {
        const recorder = mediaRecorderRef.current;
        if (!recorder || recorder.state !== "recording") return;

        if (
          lastChunkTimeRef.current &&
          Date.now() - lastChunkTimeRef.current > 2500
        ) {
          stopRecording();
        }
      }, 1000);

      setIsRecording(true);
    } catch (err) {
      console.error("Microphone error:", err);
      alert("Could not access microphone. Please check permissions.");
      setIsRecording(false);
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  }

  function toggleRecording() {
    if (loading) return;
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  /* ---------------- greeting ---------------- */

  useEffect(() => {
    if (page === "chat" && messages.length === 0) {
      const activeExperts = experts.filter(e => e && e !== "None");

      const greetingText =
        activeExperts.length === 1
          ? `👋 Hello! I’m your ${activeExperts[0]} expert. How can I help you today?`
          : `👋 Hello! I’m your ${activeExperts.join(
              ", "
            )} expert team. How can we help you today?`;

      // system message (NOT part of LLM history)
      setMessages([{ role: "system", content: greetingText }]);
    }
  }, [page]);

  /* ---------------- welcome page ---------------- */

  if (page === "welcome") {
    // Step 1: choose mode (two cards)
    if (welcomeStep === "choose") {
      return (
        <div className="welcome-screen">
          <div className="welcome-choose">
            <div className="welcome-hero">
              <div className="welcome-logo-ring">
                <ExpertCouncilIcon className="welcome-logo" />
              </div>
              <h1 className="welcome-choose-title">How would you like to chat?</h1>
              <p className="welcome-choose-subtitle">
                Pick a mode below to get started.
              </p>
            </div>
            <div className="welcome-cards">
              <button
                type="button"
                className="welcome-mode-card"
                onClick={() => setWelcomeStep("experts")}
              >
                <span className="welcome-mode-icon" aria-hidden>◇</span>
                <h2>Experts Council</h2>
                <p>
                  Name your own expert panel and get multi-perspective answers
                  that stream in real time.
                </p>
                <span className="welcome-mode-cta">Continue →</span>
              </button>
              <button
                type="button"
                className="welcome-mode-card"
                onClick={() => {
                  window.history.pushState({}, "", "#byod");
                  setByodMessages([]);
                  setByodHistory([]);
                  setByodInput("");
                  setByodUploadCollapsed(false);
                  setByodUploadFeedback(null);
                  setPage("byod");
                }}
              >
                <span className="welcome-mode-icon" aria-hidden>📄</span>
                <h2>Your documents (BYOD)</h2>
                <p>
                  Upload your own docs and ask questions with RAG. One ingest,
                  then chat.
                </p>
                <span className="welcome-mode-cta">Continue →</span>
              </button>
              <button
                type="button"
                className="welcome-mode-card"
                onClick={() => {
                  window.history.pushState({}, "", "#deep-reasoning");
                  setDeepReasoningMessages([]);
                  setDeepReasoningHistory([]);
                  setDeepReasoningInput("");
                  setPage("deepReasoning");
                }}
              >
                <span className="welcome-mode-icon" aria-hidden>🧠</span>
                <h2>Deep Reasoning</h2>
                <p>
                  Plan, solve, and review step by step. Best for complex
                  questions that need structured thinking.
                </p>
                <span className="welcome-mode-cta">Continue →</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    // Step 2: expert setup form
    return (
      <div className="welcome-screen">
        <div className="welcome-card">
          <button
            type="button"
            className="back-btn welcome-back"
            onClick={() => setWelcomeStep("choose")}
          >
            ← Back
          </button>
          <div className="welcome-header">
            <span className="brand-pill">Experts Council</span>
            <h1>Talk to a council of LLM experts.</h1>
            <p className="welcome-subtitle">
              Name the experts you want on your panel and ask any question.
              Answers stream back in real time.
            </p>
          </div>

          <div className="expert-inputs">
            {experts.map((value, index) => (
              <div key={index} className="expert-input-row">
                <label>Expert {index + 1}</label>
                <input
                  type="text"
                  placeholder={index === 0 ? "e.g. AI safety" : "Optional"}
                  value={value}
                  onChange={e => {
                    const next = [...experts];
                    const trimmed = e.target.value.trim();
                    next[index] = trimmed === "" ? "None" : e.target.value;
                    setExperts(next);
                  }}
                />
              </div>
            ))}
            <button
              type="button"
              className="secondary-btn"
              onClick={() => setExperts(prev => [...prev, "None"])}
            >
              + Add expert
            </button>
          </div>

          <button
            className="primary-btn"
            onClick={() => {
              const activeExperts = experts.filter(e => e && e !== "None");
              if (activeExperts.length === 0) {
                alert("Please enter at least one expert.");
                return;
              }
              window.history.pushState({}, "", "#chat");
              setPage("chat");
            }}
          >
            Start chatting
          </button>

          <p className="welcome-footnote">
            You can change experts any time by going back from the chat view.
          </p>
        </div>
      </div>
    );
  }

  /* ---------------- BYOD chat UI ---------------- */

  if (page === "byod") {
    return (
      <div className="app-shell">
        <header className="top-nav">
          <button
            className="back-btn"
            onClick={() => {
              window.history.pushState({}, "", "#");
              setPage("welcome");
              setByodMessages([]);
              setByodHistory([]);
              setByodInput("");
              setByodFile(null);
              setByodDocName("");
              setByodTags("");
              setByodDescription("");
            }}
          >
            ← Back to start
          </button>
          <span className="nav-title">BYOD Chat</span>
        </header>

        <main className="chat-layout">
          <section className="chat-container">
            <div className="chat-header">
              <div>
                <h2>Chat over your documents</h2>
                <p className="chat-subtitle">
                  Upload a document once, then ask questions powered by retrieval-augmented
                  generation (RAG).
                </p>
              </div>
            </div>

            <div className="byod-upload-section">
              {byodUploadCollapsed ? (
                <form
                  className="byod-upload-card byod-upload-inline"
                  onSubmit={handleByodUpload}
                >
                  <span className="byod-add-label">Add another document</span>
                  <div
                    className={`byod-drop-zone byod-drop-zone-small ${byodDragOver ? "drag-over" : ""} ${byodFile ? "has-file" : ""}`}
                    onDrop={handleByodDrop}
                    onDragOver={handleByodDragOver}
                    onDragLeave={handleByodDragLeave}
                    onClick={() => byodFileInputRef.current?.click()}
                  >
                    <input
                      ref={byodFileInputRef}
                      type="file"
                      className="byod-file-input"
                      onChange={e => setByodFile(e.target.files?.[0] || null)}
                    />
                    <span className="byod-drop-text">
                      {byodFile ? `📄 ${byodFile.name}` : "Drop file or click"}
                    </span>
                  </div>
                  <input
                    type="text"
                    className="byod-inline-name"
                    value={byodDocName}
                    onChange={e => setByodDocName(e.target.value)}
                    placeholder="Doc name (optional)"
                  />
                  {byodUploadFeedback && (
                    <div
                      className={`byod-feedback ${byodUploadFeedback.type === "error" ? "byod-feedback-error" : "byod-feedback-success"}`}
                    >
                      {byodUploadFeedback.message}
                    </div>
                  )}
                  <button
                    type="submit"
                    className="primary-btn byod-inline-submit"
                    disabled={byodUploading || !byodFile}
                  >
                    {byodUploading ? "Ingesting…" : "Ingest"}
                  </button>
                </form>
              ) : (
                <form className="byod-upload-card" onSubmit={handleByodUpload}>
                  <div
                    className={`byod-drop-zone ${byodDragOver ? "drag-over" : ""} ${byodFile ? "has-file" : ""}`}
                    onDrop={handleByodDrop}
                    onDragOver={handleByodDragOver}
                    onDragLeave={handleByodDragLeave}
                    onClick={() => byodFileInputRef.current?.click()}
                  >
                    <input
                      ref={byodFileInputRef}
                      type="file"
                      className="byod-file-input"
                      onChange={e => setByodFile(e.target.files?.[0] || null)}
                    />
                    {byodFile ? (
                      <span className="byod-drop-text">📄 {byodFile.name}</span>
                    ) : (
                      <span className="byod-drop-text">
                        Drop a file here or click to browse
                      </span>
                    )}
                  </div>
                  <div className="byod-upload-grid">
                    <label className="byod-label">
                      Document name (optional)
                      <input
                        type="text"
                        value={byodDocName}
                        onChange={e => setByodDocName(e.target.value)}
                        placeholder="e.g. Product spec v1"
                      />
                    </label>
                    <label className="byod-label">
                      Tags (optional)
                      <input
                        type="text"
                        value={byodTags}
                        onChange={e => setByodTags(e.target.value)}
                        placeholder='e.g. "spec, internal"'
                      />
                    </label>
                    <label className="byod-label byod-label-full">
                      Description (optional)
                      <textarea
                        value={byodDescription}
                        onChange={e => setByodDescription(e.target.value)}
                        placeholder="Short description for this document."
                        rows={2}
                      />
                    </label>
                  </div>
                  {byodUploadFeedback && (
                    <div
                      className={`byod-feedback ${byodUploadFeedback.type === "error" ? "byod-feedback-error" : "byod-feedback-success"}`}
                    >
                      {byodUploadFeedback.message}
                    </div>
                  )}
                  <button
                    type="submit"
                    className="primary-btn byod-submit-btn"
                    disabled={byodUploading || !byodFile}
                  >
                    {byodUploading ? "Ingesting…" : "Ingest document"}
                  </button>
                </form>
              )}
            </div>

            <div
              ref={messagesRef}
              className="messages"
              role="log"
              aria-live="polite"
            >
              <div className="messages-inner">
                {byodMessages.map((m, i) => (
                  <div
                    key={`${m.role}-byod-${i}`}
                    className={`bubble ${
                      m.role === "system" ? "assistant" : m.role
                    } ${m.justSent ? "just-sent" : ""}`}
                  >
                    <div className="bubble-content">
                      {m.content || (m.role === "assistant" ? "…" : "")}
                    </div>
                  </div>
                ))}
                <div
                  ref={scrollAnchorRef}
                  className="scroll-anchor"
                  aria-hidden="true"
                />
              </div>
            </div>

            <div className="chat-footer">
              <div className="input-area">
                <input
                  type="text"
                  value={byodInput}
                  onChange={e => setByodInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && sendByodMessage()}
                  placeholder={
                    byodLoading
                      ? "Answering from your documents..."
                      : "Ask a question about your document..."
                  }
                  disabled={byodLoading}
                />
                <button
                  onClick={sendByodMessage}
                  disabled={byodLoading || !byodInput.trim()}
                >
                  {byodLoading ? "Thinking…" : "Send"}
                </button>
              </div>
              <p className="chat-hint">
                Upload at least one document, then start asking questions.
              </p>
            </div>
          </section>
        </main>
      </div>
    );
  }

  /* ---------------- Deep Reasoning chat UI ---------------- */

  if (page === "deepReasoning") {
    return (
      <div className="app-shell">
        <header className="top-nav">
          <button
            className="back-btn"
            onClick={() => {
              window.history.pushState({}, "", "#");
              setPage("welcome");
              setDeepReasoningMessages([]);
              setDeepReasoningHistory([]);
              setDeepReasoningInput("");
            }}
          >
            ← Back to start
          </button>
          <span className="nav-title">Deep Reasoning</span>
        </header>

        <main className="chat-layout">
          <section className="chat-container">
            <div className="chat-header">
              <div>
                <h2>Plan, solve, and review</h2>
                <p className="chat-subtitle">
                  Ask complex questions. The assistant will plan steps, solve step by step,
                  and optionally review and refine the answer.
                </p>
              </div>
            </div>

            <div
              ref={messagesRef}
              className="messages"
              role="log"
              aria-live="polite"
            >
              <div className="messages-inner">
                {deepReasoningMessages.map((m, i) => (
                  <div
                    key={`${m.role}-dr-${i}`}
                    className={`bubble ${
                      m.role === "system" ? "assistant" : m.role
                    } ${m.justSent ? "just-sent" : ""}`}
                  >
                    {m.role === "assistant" && (m.showPlan || m.planFadingOut) && (m.planContent || "").trim() ? (
                      <>
                        <div
                          className={`bubble-content bubble-plan-preview${m.planFadingOut ? " bubble-plan-preview--hiding" : ""}`}
                          aria-live="polite"
                          onAnimationEnd={e => {
                            if (e.animationName === "bubble-plan-fade-out" && m.planFadingOut) {
                              setDeepReasoningMessages(prev =>
                                prev.map(msg =>
                                  msg.role === "assistant" && msg.turnId === m.turnId && msg.planFadingOut
                                    ? { ...msg, showPlan: false, planFadingOut: false }
                                    : msg
                                )
                              );
                            }
                          }}
                        >
                          {m.planContent}
                        </div>
                        <div className="bubble-content">
                          {(m.content || "").trim() ? m.content : "…"}
                        </div>
                      </>
                    ) : (
                      <div className="bubble-content">
                        {m.role === "assistant"
                          ? (m.content || "").trim() || "…"
                          : m.content}
                      </div>
                    )}
                  </div>
                ))}
                <div
                  ref={scrollAnchorRef}
                  className="scroll-anchor"
                  aria-hidden="true"
                />
              </div>
            </div>

            <div className="chat-footer">
              <div className="input-area">
                <input
                  type="text"
                  value={deepReasoningInput}
                  onChange={e => setDeepReasoningInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && sendDeepReasoningMessage()}
                  placeholder={
                    deepReasoningLoading
                      ? "Planning and solving..."
                      : "Ask a complex question..."
                  }
                  disabled={deepReasoningLoading}
                />
                <button
                  onClick={sendDeepReasoningMessage}
                  disabled={deepReasoningLoading || !deepReasoningInput.trim()}
                >
                  {deepReasoningLoading ? "Thinking…" : "Send"}
                </button>
              </div>
              <p className="chat-hint">
                Best for multi-step or analytical questions.
              </p>
            </div>
          </section>
        </main>
      </div>
    );
  }

  /* ---------------- chat UI ---------------- */

  return (
    <div className="app-shell">
      <header className="top-nav">
        <button
          className="back-btn"
          onClick={() => {
            window.history.pushState({}, "", "#");
            setPage("welcome");
            setMessages([]);
            setLlmHistory([]);
          }}
        >
          ← Change experts
        </button>
        <span className="nav-title">Experts Council</span>
      </header>

      <main className="chat-layout">
        <section className="chat-container">
          <div className="chat-header">
            <div>
              <h2>Ask your expert panel</h2>
              <p className="chat-subtitle">
                Messages stream in live from each expert so you can compare perspectives.
              </p>
            </div>

            <div className="expert-chips">
              {experts
                .filter(e => e && e !== "None")
                .map(name => (
                  <span key={name} className="expert-chip">
                    {name}
                  </span>
                ))}
            </div>
          </div>

          <div ref={messagesRef} className="messages" role="log" aria-live="polite">
            <div className="messages-inner">
              {messages.map((m, i) => (
                <div
                  key={`${m.role}-${m.expert ?? "system"}-${m.turnId ?? i}`}
                  className={`bubble ${
                    m.role === "system" ? "assistant" : m.role
                  } ${m.justSent ? "just-sent" : ""}`}
                >
                  {m.expert && <div className="bubble-meta">{m.expert}</div>}
                  <div className="bubble-content">
                    {m.content || (m.role === "assistant" ? "…" : "")}
                  </div>
                </div>
              ))}
              <div ref={scrollAnchorRef} className="scroll-anchor" aria-hidden="true" />
            </div>
          </div>

          <div className="chat-footer">
            <div className="input-area">
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && sendMessage()}
                placeholder={
                  loading ? "Experts are thinking..." : "Ask a question..."
                }
                disabled={loading}
              />
              <div className="attachment-controls">
                <input
                  ref={visionFileInputRef}
                  id="chat-vision-upload"
                  className="attachment-input-hidden"
                  type="file"
                  accept="image/*"
                  onChange={e => setVisionFile(e.target.files?.[0] || null)}
                />
                <button
                  type="button"
                  className={`attachment-button ${visionFile ? "has-file" : ""}`}
                  onClick={() => visionFileInputRef.current?.click()}
                  disabled={loading}
                >
                  <span aria-hidden>📎</span>
                  <span className="attachment-label">
                    {visionFile ? "Image attached" : "Attach image"}
                  </span>
                </button>
              </div>
              <button
                type="button"
                className={`icon-button ${isRecording ? "mic-active" : ""}`}
                onClick={toggleRecording}
                disabled={loading}
              >
                {isRecording ? "■" : "🎙"}
              </button>
              <button
                onClick={sendMessage}
                disabled={loading || (!input.trim() && !visionFile)}
              >
                {loading ? "Thinking…" : "Send"}
              </button>
            </div>
            <p className="chat-hint">
              Press Enter to send text, or attach an image with text for vision analysis.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
