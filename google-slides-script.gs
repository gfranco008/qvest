const TITLE = "QVest Reading Momentum POC";
const SUBTITLE = "Agentic Library Concierge + Tools";
// Optional: provide publicly accessible image URLs for visuals.
const ARCH_IMAGE_URL = "";
const TRACE_UI_IMAGE_URL = "";
const UI_SCREENSHOT_URL = "";

const THEME = {
  titleFont: "Montserrat",
  bodyFont: "Roboto",
  accent: "#C17B37",
  dark: "#1F1C1B",
  muted: "#5F5A55",
  panel: "#FFF6EA",
};

function createQvestDeck() {
  const pres = SlidesApp.create(TITLE);
  pres.getSlides().forEach((slide) => slide.remove());

  addTitleSlide(pres, TITLE, SUBTITLE, [
    "Personalized recommendations from lending history",
    "Explainable, librarian-friendly outputs",
    "Lightweight, demo-ready architecture",
  ]);

  addSectionSlide(pres, "Context");
  addBulletsSlide(pres, "Problem", [
    "Librarians need fast, trustworthy recommendations",
    "Student profiles are incomplete or outdated",
    "Inventory, holds, and feedback are siloed",
    "Hard to explain why a book was suggested",
  ]);

  addBulletsSlide(pres, "What This POC Shows", [
    "Co-borrowing recommender with transparent reasons",
    "Agentic workflow combining tools + context",
    "Optional LLM layer for tone and summarization",
    "Live UI for concierge, onboarding, holds, gaps, feedback",
  ]);

  addSectionSlide(pres, "Demo");
  addBulletsSlide(pres, "Demo Story", [
    "Select a student and request recommendations",
    "Run onboarding from reading history",
    "Ask for availability and place a hold",
    "Capture feedback and show the loop",
    "Open the trace panel to explain the response",
  ]);

  addSectionSlide(pres, "Architecture");
  addBulletsSlide(pres, "System Overview", [
    "FastAPI backend + static frontend",
    "CSV catalog, students, loans",
    "Deterministic recommender + optional LLM",
    "Agent tools for availability, history, onboarding, holds",
  ]);

  addImageSlide(
    pres,
    "Agentic + Tools Architecture",
    ARCH_IMAGE_URL,
    "Insert architecture diagram here"
  );

  addBulletsSlide(pres, "Agent Engine Highlights", [
    "Intent policy and tool routing",
    "Shared context builder for consistency",
    "Guardrails: no fabrication, privacy-aware",
    "Observability logs for every run",
  ]);

  addBulletsSlide(pres, "Tools Layer", [
    "Availability tool",
    "Reading history tool",
    "Onboarding from history tool",
    "Student snapshot tool",
    "Series/author continuation tool",
    "Hold placement tool",
  ]);

  addBulletsSlide(pres, "Recommender + Explanations", [
    "Co-borrowing similarity signals",
    "Clear, human-readable reasons",
    "Optional LLM for tone and summary",
    "No black box ranking in the demo",
  ]);

  addImageSlide(
    pres,
    "Observability + Trace UI",
    TRACE_UI_IMAGE_URL,
    "Insert trace panel screenshot here"
  );

  addImageSlide(
    pres,
    "Agent Lab UI",
    UI_SCREENSHOT_URL,
    "Insert UI screenshot here"
  );

  addSectionSlide(pres, "Why It Works");
  addBulletsSlide(pres, "Why This Works for Pilot", [
    "Runs locally and is easy to demo",
    "Deterministic core with optional LLM",
    "Transparent explanations for stakeholders",
    "Clear upgrade path to production",
  ]);

  addSectionSlide(pres, "Next Steps");
  addBulletsSlide(pres, "Roadmap", [
    "Add evaluations and scripted demo flows",
    "Expand recommendation signals",
    "Integrate live catalog data",
    "Add multi-school dashboards",
    "Harden guardrails and policy controls",
  ]);

  addSectionSlide(pres, "Decision");
  addBulletsSlide(pres, "Ask", [
    "Approve pilot scope and success metrics",
    "Identify two schools for early rollout",
    "Align on data access and privacy constraints",
  ]);

  addTitleSlide(pres, "Q&A", "Thank you.", []);

  Logger.log(pres.getUrl());
}

function addTitleSlide(pres, title, subtitle, bullets) {
  const slide = pres.appendSlide(SlidesApp.PredefinedLayout.TITLE_AND_BODY);
  slide
    .getPlaceholder(SlidesApp.PlaceholderType.TITLE)
    .asShape()
    .getText()
    .setText(title);
  const body = slide.getPlaceholder(SlidesApp.PlaceholderType.BODY).asShape().getText();

  if (bullets && bullets.length) {
    const lines = bullets.map((item) => `- ${item}`).join("\n");
    body.setText(subtitle + "\n\n" + lines);
  } else {
    body.setText(subtitle);
  }
  styleTitle(slide);
  styleBody(body);
  return slide;
}

function addBulletsSlide(pres, title, bullets) {
  const slide = pres.appendSlide(SlidesApp.PredefinedLayout.TITLE_AND_BODY);
  slide
    .getPlaceholder(SlidesApp.PlaceholderType.TITLE)
    .asShape()
    .getText()
    .setText(title);
  const body = slide.getPlaceholder(SlidesApp.PlaceholderType.BODY).asShape().getText();
  const lines = bullets.map((item) => `- ${item}`).join("\n");
  body.setText(lines);
  styleTitle(slide);
  styleBody(body);
  return slide;
}

function addImageSlide(pres, title, imageUrl, placeholderText) {
  const slide = pres.appendSlide(SlidesApp.PredefinedLayout.TITLE_ONLY);
  slide
    .getPlaceholder(SlidesApp.PlaceholderType.TITLE)
    .asShape()
    .getText()
    .setText(title);
  styleTitle(slide);

  if (imageUrl) {
    const image = slide.insertImage(imageUrl);
    image.setLeft(60).setTop(120).setWidth(600);
  } else {
    const box = slide.insertTextBox(placeholderText, 80, 140, 560, 240);
    box.getText().getTextStyle().setFontSize(20).setForegroundColor("#6b4a2c");
  }
  return slide;
}

function addSectionSlide(pres, label) {
  const slide = pres.appendSlide(SlidesApp.PredefinedLayout.SECTION_HEADER);
  const title = slide.getPlaceholder(SlidesApp.PlaceholderType.TITLE).asShape().getText();
  title.setText(label);
  title
    .getTextStyle()
    .setFontFamily(THEME.titleFont)
    .setFontSize(52)
    .setForegroundColor(THEME.dark);
  const body = slide.getPlaceholder(SlidesApp.PlaceholderType.BODY);
  if (body) {
    body.asShape().getText().setText("");
  }
  return slide;
}

function styleTitle(slide) {
  const title = slide.getPlaceholder(SlidesApp.PlaceholderType.TITLE);
  if (!title) return;
  title
    .asShape()
    .getText()
    .getTextStyle()
    .setFontFamily(THEME.titleFont)
    .setFontSize(36)
    .setForegroundColor(THEME.dark);
}

function styleBody(bodyText) {
  bodyText
    .getTextStyle()
    .setFontFamily(THEME.bodyFont)
    .setFontSize(20)
    .setForegroundColor(THEME.muted);
}
