"use client";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Lightbulb,
  Quote,
  Pencil,
  CornerDownRight,
} from "lucide-react";
import type { Application, Answer, Achievement } from "@/lib/careerproof/types";
import { questionAt } from "@/lib/careerproof/demo-service";
import { Badge, ContinueButton } from "./ui";
export function Questions({
  app,
  onAnswer,
  onAddEvidence,
  onContinue,
}: {
  app: Application;
  onAnswer: (a: Answer) => void;
  onAddEvidence: (e: Achievement) => void;
  onContinue: () => void;
}) {
  const [index, setIndex] = useState(Math.min(app.answers.length, 4));
  const [text, setText] = useState("");
  const [choice, setChoice] = useState("");
  const [where, setWhere] = useState("");
  const [result, setResult] = useState("");
  const q = questionAt(Math.min(index, 3), app.answers);
  function navigate(i: number) {
    const previous = app.answers.find((a) => a.id === i + 1);
    setIndex(i);
    setText(previous?.contribution || previous?.text || "");
    setChoice(previous?.choice || "");
    setWhere(previous?.location || "");
    setResult(previous?.outcome || "");
  }
  function submit(skipped = false) {
    const answer: Answer = {
      location: where,
      outcome: result,
      contribution: text,
      id: q.id,
      prompt: q.prompt,
      text: skipped
        ? ""
        : q.kind === "detail"
          ? `${where}: ${text}${result ? ` ${result}` : ""}`
          : text,
      choice: skipped ? undefined : choice,
      skipped,
    };
    onAnswer(answer);
    if (q.kind === "detail" && !skipped) {
      const professional =
        app.answers.find((a) => a.id === 3)?.choice === "professional";
      onAddEvidence({
        id: "redis-answer",
        text: `${text}${result ? ` ${result}` : ""}`,
        company: where,
        role: professional ? "Candidate contribution" : "Personal project",
        section: professional ? "Experience" : "Projects",
        skills: ["Redis"],
        sourceIds: [],
        excerpt: `Candidate confirmed ${professional ? "professional" : "project"} use of Redis at ${where}. ${text} ${result}`,
        origin: "answer",
        depth: professional ? "professional" : "personal_project",
        revision: 1,
      });
    }
    setIndex(index + 1);
    setText("");
    setChoice("");
    setWhere("");
    setResult("");
  }
  return (
    <div className="question-layout">
      <section className="question-main main-surface">
        {index < 4 ? (
          <>
            <div className="question-progress">
              <span className="step-kicker">A LITTLE MORE CONTEXT</span>
              <Badge>{index + 1} of 4 questions</Badge>
            </div>
            <div className="question-bars">
              {[0, 1, 2, 3].map((i) => (
                <span key={i} className={i <= index ? "filled" : ""} />
              ))}
            </div>
            <div className="question-heading">
              <span className="question-number">0{index + 1}</span>
              <h2>{q.prompt}</h2>
            </div>
            <div className="question-benefit">
              <Lightbulb size={19} strokeWidth={1.5} />
              <div>
                <strong>How this helps you</strong>
                <p>{q.benefit}</p>
              </div>
            </div>
            {q.choices ? (
              <fieldset className="choice-list">
                <legend className="visually-hidden">{q.prompt}</legend>
                {q.choices.map((c) => (
                  <label
                    className={`choice ${choice === c.value ? "selected" : ""}`}
                    key={c.value}
                  >
                    <input
                      type="radio"
                      name="question-choice"
                      value={c.value}
                      checked={choice === c.value}
                      onChange={() => setChoice(c.value)}
                    />
                    <span>
                      <strong>{c.label}</strong>
                      <small>{c.description}</small>
                    </span>
                    {choice === c.value && <Check size={17} />}
                  </label>
                ))}
              </fieldset>
            ) : (
              <div className="question-fields">
                {q.kind === "detail" && (
                  <label>
                    Project or employer name
                    <input
                      value={where}
                      onChange={(e) => setWhere(e.target.value)}
                      placeholder="Where did this work happen?"
                    />
                  </label>
                )}
                <label>
                  {q.kind === "detail"
                    ? "What did you personally do?"
                    : "In your own words"}
                  <textarea
                    rows={4}
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={
                      index === 0
                        ? "What was slow? What did you change? How did you know it helped?"
                        : "Focus on your contribution, not everything the team delivered."
                    }
                  />
                </label>
                {q.kind === "detail" && (
                  <label>
                    What changed? <span className="muted">Optional</span>
                    <input
                      value={result}
                      onChange={(e) => setResult(e.target.value)}
                      placeholder="A qualitative outcome is just as useful as a metric."
                    />
                  </label>
                )}
                <button
                  className="inline-link"
                  onClick={() => {
                    if (q.kind === "detail") {
                      setWhere("Personal API project");
                      setText(
                        "Used Redis to store responses for repeated API requests.",
                      );
                      setResult(
                        "Checked cache hits and compared repeat-request response times locally.",
                      );
                    } else
                      setText(
                        "I stored responses and reused them for repeated requests. I compared the response times locally before and after the change.",
                      );
                  }}
                >
                  Use a fictional sample answer <CornerDownRight size={13} />
                </button>
              </div>
            )}
            {index < app.answers.length && (
              <p className="notice">
                Editing this answer will reopen any dependent questions and flag
                affected drafts. Submitted versions stay unchanged.
              </p>
            )}
            <div className="question-actions">
              <button
                className="button ghost"
                disabled={index === 0}
                onClick={() => navigate(index - 1)}
              >
                <ArrowLeft size={15} />
                Back
              </button>
              <div>
                <button className="button ghost" onClick={() => submit(true)}>
                  Skip for now
                </button>
                <button
                  className="button primary"
                  disabled={
                    q.choices
                      ? !choice
                      : !text.trim() || (q.kind === "detail" && !where.trim())
                  }
                  onClick={() => submit()}
                >
                  Save and continue
                  <ArrowRight size={15} />
                </button>
              </div>
            </div>
            <p className="micro question-footnote">
              Four questions maximum, including follow-ups. No answer is better
              than an invented one.
            </p>
          </>
        ) : (
          <div className="questions-complete">
            <span className="completion-mark">
              <Check size={28} />
            </span>
            <p className="eyebrow">CONTEXT CAPTURED</p>
            <h2>Your work has a little more room to speak.</h2>
            <p className="muted">
              Your answers stay with the relevant achievement. Now review how
              they shape the resume.
            </p>
            <div className="answer-list">
              {app.answers.map((a) => (
                <button key={a.id} onClick={() => navigate(a.id - 1)}>
                  <span>0{a.id}</span>
                  <div>
                    <strong>{a.prompt}</strong>
                    <small>
                      {a.skipped
                        ? "Skipped · no new claim added"
                        : a.choice
                          ? a.choice.replaceAll("_", " ")
                          : a.text}
                    </small>
                  </div>
                  <Pencil size={14} />
                </button>
              ))}
            </div>
            <ContinueButton onClick={onContinue}>
              Review your tailored resume
            </ContinueButton>
          </div>
        )}
      </section>
      <aside className="context-panel question-aside">
        <span className="eyebrow">THE SOURCE OF THIS QUESTION</span>
        <Quote size={24} strokeWidth={1.3} className="quote-mark" />
        <blockquote>
          Made repeated API requests faster by reusing stored results.
        </blockquote>
        <p className="micro">Alex_Morgan_Projects.pdf · Personal API project</p>
        <div className="panel-divider" />
        <h4>You don’t need the perfect words.</h4>
        <p className="muted">
          Describe the work as you remember it. We’ll suggest terminology, and
          you decide whether it’s accurate.
        </p>
        <div className="quiet-note">
          <p>
            <strong>Personal project ≠ professional experience.</strong>
            <br />
            Your answer’s context follows it into every draft.
          </p>
        </div>
      </aside>
    </div>
  );
}
