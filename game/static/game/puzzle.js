// The puzzle page: shows the state the server sends, and posts the player's guesses.
//
// The server decides what that state holds. Years, article links and the source
// page arrive only under `state.reveal`, once the puzzle is over, so nothing in
// this file can show them early. Everything is built with textContent, never
// innerHTML, so event text can't inject markup.

const RIGHT = "🟩";
const WRONG = "⬜";
const WIKIPEDIA = "https://en.wikipedia.org/";

/** Posts guesses to the game API. */
class PuzzleApi {
  async guess(date, order) {
    let response;
    try {
      response = await fetch(`/api/puzzle/${date}/guess`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": PuzzleApi.csrfToken() },
        body: JSON.stringify({ order }),
      });
    } catch {
      throw new Error("Couldn't reach the server. Check your connection and try again.");
    }

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.error ?? `Something went wrong (${response.status}). Try again.`);
    }
    return body;
  }

  /** Django's CSRF token, from the cookie the page sets. */
  static csrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }
}

/** Slides tiles between places instead of letting them jump. */
class Motion {
  static DURATION = 150; // ms

  static get reduced() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  /**
   * Runs `change`, then slides each of `tiles` from where it was drawn to where
   * it now sits. (The "FLIP" technique: measure, change, invert, play.)
   */
  static reorder(tiles, change) {
    const before = new Map(tiles.map((tile) => [tile, tile.getBoundingClientRect().top]));
    // A tile still sliding from the last change starts from where it is drawn now.
    tiles.forEach((tile) => tile.getAnimations().forEach((animation) => animation.cancel()));
    change();
    if (Motion.reduced) return;

    for (const tile of tiles) {
      const shift = before.get(tile) - tile.getBoundingClientRect().top;
      if (Math.abs(shift) < 1) continue;
      tile.animate([{ transform: `translateY(${shift}px)` }, { transform: "none" }], {
        duration: Motion.DURATION,
        easing: "ease-out",
      });
    }
  }

  /** Glides a dropped tile from `from`, where it was drawn, into its place. */
  static settle(tile, from) {
    if (Motion.reduced) return;
    const to = tile.getBoundingClientRect();
    tile.animate(
      [{ transform: `translate(${from.left - to.left}px, ${from.top - to.top}px)` }, { transform: "none" }],
      { duration: Motion.DURATION, easing: "ease-out" },
    );
  }
}

/**
 * Drag to reorder. The picked-up tile follows the pointer up and down, and the
 * others slide aside to open a gap where it will land.
 *
 * A mouse can grab a tile anywhere but its buttons. A finger has to use the
 * handle, so a swipe elsewhere on a tile still scrolls the page.
 */
class DragSorter {
  static THRESHOLD = 4; // px the pointer must move before a press becomes a drag

  constructor(list, onDrop) {
    this.list = list;
    this.onDrop = onDrop;
    this.pressed = null; // { tile, startY }: pointer down, not yet moved far enough
    this.drag = null; // { tile, placeholder, grabOffset }: a tile is being dragged

    list.addEventListener("pointerdown", (event) => this.press(event));
    list.addEventListener("pointermove", (event) => this.move(event));
    list.addEventListener("pointerup", () => this.release());
    list.addEventListener("pointercancel", () => this.release());
  }

  press(event) {
    if (event.button !== 0 || this.drag || event.target.closest("button")) return;
    const grip = event.pointerType === "mouse" ? ".event" : ".handle";
    if (!event.target.closest(grip)) return;

    event.preventDefault(); // no text selection, no scrolling
    const tile = event.target.closest(".event");
    // Pointer events keep coming to the tile even when the pointer leaves it.
    tile.setPointerCapture(event.pointerId);
    this.pressed = { tile, startY: event.clientY };
  }

  move(event) {
    if (this.pressed && !this.drag) {
      if (Math.abs(event.clientY - this.pressed.startY) < DragSorter.THRESHOLD) return;
      this.lift(this.pressed.tile, this.pressed.startY);
    }
    if (!this.drag) return;

    this.drag.tile.style.top = `${event.clientY - this.drag.grabOffset}px`;
    this.movePlaceholder();
  }

  release() {
    if (this.drag) this.drop();
    this.pressed = null;
  }

  /** Takes the tile out of the list's flow and leaves a gap of the same size. */
  lift(tile, pointerY) {
    tile.getAnimations().forEach((animation) => animation.cancel());
    const box = tile.getBoundingClientRect();

    const placeholder = document.createElement("li");
    placeholder.className = "placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    placeholder.style.height = `${box.height}px`;
    tile.before(placeholder);

    tile.classList.add("dragging");
    Object.assign(tile.style, {
      left: `${box.left}px`,
      top: `${box.top}px`,
      width: `${box.width}px`,
    });
    document.body.classList.add("dragging");
    this.drag = { tile, placeholder, grabOffset: pointerY - box.top };
  }

  /** Moves the gap to wherever the middle of the dragged tile now is. */
  movePlaceholder() {
    const { tile, placeholder } = this.drag;
    const box = tile.getBoundingClientRect();
    const middle = box.top + box.height / 2;

    // Compare against where the other tiles sit in the layout, not where they
    // are drawn mid-slide, or the gap would flicker back and forth.
    const others = this.tiles().filter((other) => other !== tile);
    const listTop = this.list.getBoundingClientRect().top;
    const next =
      others.find((other) => middle < listTop + other.offsetTop + other.offsetHeight / 2) ?? null;

    if (this.nextTile(placeholder) === next) return;
    Motion.reorder([...others, placeholder], () => this.list.insertBefore(placeholder, next));
  }

  /** Puts the tile into the gap and lets it glide there from the pointer. */
  drop() {
    const { tile, placeholder } = this.drag;
    const from = tile.getBoundingClientRect();

    placeholder.replaceWith(tile);
    tile.classList.remove("dragging");
    tile.style.cssText = "";
    document.body.classList.remove("dragging");
    this.drag = null;

    Motion.settle(tile, from);
    this.onDrop();
  }

  tiles() {
    return [...this.list.querySelectorAll(":scope > .event")];
  }

  /** The tile after `element` in the list, skipping the one being dragged. */
  nextTile(element) {
    let sibling = element.nextElementSibling;
    while (sibling && (sibling === this.drag.tile || !sibling.classList.contains("event"))) {
      sibling = sibling.nextElementSibling;
    }
    return sibling;
  }
}

/** The list being ordered: drag the events, or use their arrow buttons. */
class EventList {
  constructor(element) {
    this.element = element;
    this.rightPlaces = new Map(); // event id -> the place the last guess had it right
    this.sorter = new DragSorter(element, () => this.markRightPlaces());

    element.addEventListener("click", (event) => this.moveWithButton(event));
  }

  render(events, lastGuess) {
    this.rightPlaces = new Map();
    lastGuess?.order.forEach((id, index) => {
      if (lastGuess.correct[index]) this.rightPlaces.set(id, index);
    });
    this.element.replaceChildren(...events.map((event) => EventList.item(event)));
    this.markRightPlaces();
  }

  tiles() {
    return [...this.element.querySelectorAll(":scope > .event")];
  }

  /** Event ids in the order they're shown now. */
  order() {
    return this.tiles().map((tile) => tile.dataset.id);
  }

  static item(event) {
    const item = document.createElement("li");
    item.className = "event";
    item.dataset.id = event.id;

    const handle = document.createElement("span");
    handle.className = "handle";
    handle.textContent = "⠿";
    handle.setAttribute("aria-hidden", "true");

    const text = document.createElement("span");
    text.className = "text";
    text.textContent = event.text;

    item.append(
      handle,
      text,
      EventList.moveButton("up", "↑", "Move earlier"),
      EventList.moveButton("down", "↓", "Move later"),
    );
    return item;
  }

  static moveButton(direction, symbol, label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "move";
    button.dataset.move = direction;
    button.textContent = symbol;
    button.setAttribute("aria-label", label);
    return button;
  }

  /** Green stays on an event only while it sits where the last guess had it right. */
  markRightPlaces() {
    this.tiles().forEach((tile, index) => {
      tile.classList.toggle("right", this.rightPlaces.get(tile.dataset.id) === index);
    });
  }

  moveWithButton(event) {
    const button = event.target.closest("button[data-move]");
    if (!button) return;

    const tile = button.closest(".event");
    const neighbour =
      button.dataset.move === "up" ? tile.previousElementSibling : tile.nextElementSibling;
    if (!neighbour) return;

    Motion.reorder(this.tiles(), () => {
      if (button.dataset.move === "up") neighbour.before(tile);
      else neighbour.after(tile);
    });
    button.focus(); // moving the tile in the page drops keyboard focus
    this.markRightPlaces();
  }
}

/** One row of squares per try, showing which places were right. */
class GuessHistory {
  constructor(element) {
    this.element = element;
  }

  render(guesses) {
    this.element.hidden = guesses.length === 0;
    this.element.replaceChildren(
      ...guesses.map((guess) => {
        const right = guess.correct.filter(Boolean).length;
        const row = document.createElement("p");
        row.className = "row";
        row.textContent = `${guess.correct.map((ok) => (ok ? RIGHT : WRONG)).join("")}  ${right} of ${guess.correct.length} right`;
        return row;
      }),
    );
  }
}

/** The answer, once the puzzle is over: years, article links, and the share text. */
class RevealPanel {
  constructor(element) {
    this.element = element;
    this.message = element.querySelector('[data-reveal="message"]');
    this.list = element.querySelector('[data-reveal="events"]');
    this.source = element.querySelector('[data-reveal="source"]');
    this.shareText = element.querySelector('[data-reveal="share-text"]');
    this.shareStatus = element.querySelector('[data-reveal="share-status"]');
    element
      .querySelector('[data-reveal="share-button"]')
      .addEventListener("click", () => this.copyShareText());
  }

  render(state) {
    const reveal = state.reveal;
    this.element.hidden = !reveal;
    if (!reveal) return;

    this.message.textContent =
      state.status === "solved"
        ? `Solved in ${state.guesses.length} of ${state.max_attempts}.`
        : "Out of tries. Here's the order:";
    this.list.replaceChildren(...reveal.events.map((event) => RevealPanel.item(event)));
    this.source.href = RevealPanel.safeUrl(reveal.source_url) ?? WIKIPEDIA;
    this.shareText.textContent = reveal.share;
  }

  static item(event) {
    const item = document.createElement("li");

    const year = document.createElement("strong");
    year.className = "year";
    year.textContent = event.year_label;

    const text = document.createElement("span");
    text.textContent = ` ${event.text}`;

    const links = document.createElement("ul");
    links.className = "articles";
    for (const article of event.articles) {
      const url = RevealPanel.safeUrl(article.url);
      if (!url) continue;
      const link = document.createElement("a");
      link.href = url;
      link.textContent = article.title;
      const entry = document.createElement("li");
      entry.append(link);
      links.append(entry);
    }

    item.append(year, text, links);
    return item;
  }

  /** Only links into Wikipedia are followed; anything else is dropped. */
  static safeUrl(url) {
    return typeof url === "string" && url.startsWith(WIKIPEDIA) ? url : null;
  }

  async copyShareText() {
    try {
      await navigator.clipboard.writeText(this.shareText.textContent);
      this.shareStatus.textContent = "Copied.";
    } catch {
      this.shareStatus.textContent = "Couldn't copy. Select the text above instead.";
    }
  }
}

/** Wires the parts together: renders the state, sends a guess, renders the answer. */
class PuzzleGame {
  constructor(state) {
    this.state = state;
    this.api = new PuzzleApi();
    this.playArea = document.getElementById("play");
    this.status = document.getElementById("status");
    this.events = new EventList(document.getElementById("events"));
    this.history = new GuessHistory(document.getElementById("history"));
    this.reveal = new RevealPanel(document.getElementById("reveal"));
    this.submitButton = document.getElementById("submit");
    this.error = document.getElementById("error");

    this.submitButton.addEventListener("click", () => this.submit());
  }

  render() {
    const playing = this.state.status === "playing";
    this.playArea.hidden = !playing;
    if (playing) {
      this.status.textContent = PuzzleGame.triesLeft(this.state.attempts_left);
      this.events.render(this.state.events, this.state.guesses.at(-1));
    }
    this.history.render(this.state.guesses);
    this.reveal.render(this.state);
  }

  async submit() {
    this.submitButton.disabled = true;
    this.showError("");
    try {
      this.state = await this.api.guess(this.state.date, this.events.order());
      this.render();
    } catch (error) {
      this.showError(error.message);
    } finally {
      this.submitButton.disabled = false;
    }
  }

  showError(message) {
    this.error.textContent = message;
    this.error.hidden = !message;
  }

  static triesLeft(count) {
    return count === 1 ? "1 try left" : `${count} tries left`;
  }
}

const state = JSON.parse(document.getElementById("puzzle-state").textContent);
new PuzzleGame(state).render();
