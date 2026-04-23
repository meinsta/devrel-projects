# Voice Profile

This file has two parts:
1. **Guardrails** -- universal rules to avoid AI-generated slop. These
   apply to ALL voices and are non-negotiable.
2. **Voice Identity** -- the specific voice for THIS novel. Generated
   during the foundation phase. Could be anything: dense and mythic,
   spare and brutal, warm and whimsical. The voice emerges from the
   story's needs.

---

## Part 1: Guardrails (permanent, all novels)

These are the cliff edges. Stay away from them regardless of voice.

### Tier 1: Banned words -- kill on sight

These are statistically overrepresented in LLM output vs. human writing.
If one appears, rewrite the sentence. No exceptions.

| Kill this         | Use instead                                    |
|-------------------|------------------------------------------------|
| delve             | dig into, examine, look at                     |
| utilize           | use                                            |
| leverage (verb)   | use, take advantage of                         |
| facilitate        | help, enable, make possible                    |
| elucidate         | explain, clarify                               |
| embark            | start, begin                                   |
| endeavor          | effort, try                                    |
| encompass         | include, cover                                 |
| multifaceted      | complex, varied                                |
| tapestry          | (describe the actual thing)                    |
| testament to      | shows, proves, demonstrates                    |
| paradigm          | model, approach, framework                     |
| synergy           | (delete the sentence and start over)           |
| holistic          | whole, complete, full-picture                  |
| catalyze          | trigger, cause, spark                          |
| juxtapose         | compare, contrast, set against                 |
| nuanced (filler)  | (cut it -- if it's nuanced, show how)          |
| realm             | area, field, domain                            |
| landscape (metaphorical) | field, space, situation                 |
| myriad            | many, lots of                                  |
| plethora          | many, a lot                                    |

### Tier 2: Suspicious in clusters

Fine alone. Three in one paragraph = rewrite that paragraph.

robust, comprehensive, seamless, cutting-edge, innovative, streamline,
empower, foster, enhance, elevate, optimize, pivotal, intricate,
profound, resonate, underscore, harness, navigate (metaphorical),
cultivate, bolster, galvanize, cornerstone, game-changer, scalable

### Tier 3: Filler phrases -- delete on sight

These add zero information. The sentence is always better without them.

- "It's worth noting that..." -> just state it
- "It's important to note that..." -> just state it
- "Importantly, ..." / "Notably, ..." / "Interestingly, ..." -> just state it
- "Let's dive into..." / "Let's explore..." -> start with the content
- "As we can see..." -> they can see
- "Furthermore, ..." / "Moreover, ..." / "Additionally, ..." -> and, also, or just start
- "In today's [fast-paced/digital/modern] world..." -> delete the clause
- "At the end of the day..." -> delete
- "It goes without saying..." -> then don't say it
- "When it comes to..." -> just talk about the thing
- "One might argue that..." -> argue it or don't
- "Not just X, but Y" -> restructure (the #1 LLM rhetorical crutch)

### Structural slop patterns

These are the shapes that betray machine origin. Avoid them in any voice.

**Paragraph template machine**: Don't repeat the same paragraph
structure (topic sentence -> elaboration -> example -> wrap-up).
Vary it. Sometimes the point comes last. Sometimes a paragraph is
one sentence. Sometimes three long ones in a row.

**Sentence length uniformity**: If every sentence is 15-25 words,
it reads as synthetic. Mix in fragments. And long, winding,
clause-heavy sentences that carry the reader through a thought
the way a river carries a leaf. Then a short one.

**Transition word addiction**: If consecutive paragraphs start with
"However," "Furthermore," "Additionally," "Moreover," "Nevertheless"
-- rewrite. Start with the subject. Start with action. Start with
dialogue. Start with a sense detail.

**Symmetry addiction**: Don't balance everything. Three pros, three
cons, five steps -- that's a tell. Real writing is lumpy. Some
sections are long because they need to be. Some are two lines.

**Hedge parade**: "may," "might," "could potentially," "it's possible
that" -- pick one per page, max. State things or don't.

**Em dash overload**: One or two per page is fine. Five per paragraph
is a dead giveaway. Use commas, parentheses, or two sentences instead.

**List abuse**: Prose, not bullets. If the scene calls for a list
(a merchant's inventory, a spell's components), earn it. Don't
default to bullet points because it's easy.

### The smell test

After writing any passage, ask:
- Read it aloud. Does it sound like a person talking?
- Is there a single surprising sentence? Human writing surprises.
- Does it say something specific? Could you swap the topic and the
  words would still work? Specificity kills slop.
- Would a reader think "AI wrote this"? If yes, rewrite.

---

## Part 2: Voice Identity (generated per novel)

Everything below is discovered during the foundation phase.
The agent proposes a voice that serves THIS story, writes exemplar
passages, and calibrates against them throughout drafting.

### Tone

Grounded warmth with a knife in its pocket.

The default register is a craftsman's eye: practical, specific, occasionally
funny in a dry way that comes from observation rather than commentary.
Cantamura is absurd — people sing their parking disputes, counterfeiting
is a musical offense — but the people who live there take it as seriously
as we take tax law. The humor is never winking at the reader. It rises from
a fourteen-year-old boy who loves a city that is slowly breaking him.

The warmth comes from Cass's love of his family, his craft, his home.
The darkness comes from what that love costs. The tone moves on a
gradient: early chapters lean whimsical and sensory (the morning market,
the bell workshop, the music academy). Later chapters tighten as Cass
discovers how deeply coercion is built into the system. The humor never
vanishes — it's how Cass survives — but it gets sharper, more defensive.

Think: a hand resting on a bell that's still vibrating. You feel the tremor
in your bones before you name the note.

### Sentence Rhythm

Short sentences carry emotional weight. They land like struck bells.

Long sentences build the world or track Cass's perception of sound —
the way a dozen overlapping frequencies press against his skull in a
crowded market, each one distinguishable if he focuses, all of them
painful if he doesn't. Let the long ones breathe and accrue.

Fragments for pain. For shock. For the moment a lie reaches his ear.

Dialogue is clipped. People in Cantamura choose their words with care
because words, once sung, can bind. Narration flows longer when Cass is
safe and tightens when he's not. Violence and danger get short, almost
airless prose. Reflection and worldbuilding get the winding sentences.

Avoid uniform sentence length above all. The rhythm should feel like
music — mixed meter, not a metronome.

### Vocabulary Register

The word-hoard draws from three wells:

**Musical craft.** Pitch, interval, key, frequency, octave, vibrato,
resonance, clapper, tuning, temperament, harmonic, dissonance, rest,
measure, bar, chord. These are workaday words for Cass, as ordinary as
"hammer" to a carpenter. Never mystify them. Never italicize them for
effect. This is his native language.

**Trade and material.** Bronze, copper, linseed oil, metal-dust, lathe,
pitch-gauge, counting-board, wax, mold, anvil, flux. Cantamura is a
city of makers. The prose should smell of a workshop, not a library.

**Body and sensation.** Jaw, ribs, temples, tongue, the roof of his
mouth, the bones behind his ears. Cass's gift lives in his body.
His pain is physical and specific — needles behind the left eye, a
greasy texture to false notes, nausea in the presence of coerced oaths.
Name the anatomy. Skip the abstraction.

**Avoid:** Generic fantasy diction ("ancient power," "dark forces,"
"the shadows deepened"). Modern slang or idiom that would break the
world ("vibes," "toxic," "literally"). Latinate abstractions where
Anglo-Saxon concreteness would do. Words that describe Cantamura as
wondrous or magical — to Cass, it's home.

### POV and Tense

Third-person limited, past tense, locked to Cass.

The narration has access to what Cass perceives, thinks, and feels.
No one else's interiority. The "camera" sits close: the prose registers
what his body does (jaw tightens, hands shake, tongue presses the roof
of his mouth) before naming the emotion. Sometimes it doesn't name the
emotion at all. Let the body speak.

Rare present-tense intrusions for truths Cass has arrived at through
hard experience: "There is a pitch the body knows before the ear does."
These are used like a bell struck in an otherwise quiet room — seldom,
and always earned.

No omniscient intrusions. No "little did he know." No narrative voice
that exists outside Cass's perception. If Cass doesn't notice it, the
prose doesn't mention it.

### Dialogue Conventions

**Tags:** "Said" as default. Action beats to replace tags when the
physical gesture matters more than the speech. No adverbs on dialogue
tags. Ever. "He said quietly" becomes a gesture — he drops his voice,
or leans closer, or the words barely clear his teeth.

**Subtext carries the weight.** Cantamura has taught its citizens the
cost of direct speech. Words sung aloud can become binding. So people
talk around the thing. The father says "Hand me the pitch-gauge" when
he means "I can't talk about your brother." Cass asks a practical
question when he means "Why did you let this happen?" The reader
should hear the unsaid thing louder than the spoken one.

**Character differentiation.** Cass speaks shorter than he thinks.
He's learned to keep his mouth shut in a city where speech has legal
force. His father speaks in instructions and trade-talk — a man who
has retreated into his craft. Song-brokers are voluble, precise,
performative. Academy students are formal, competitive, prone to
showing off their training with overly correct phrasing.

**No dialect spelling.** No dropped g's, no phonetic quirks. Character
voice comes from word choice, sentence length, and what they refuse
to say.

### Exemplar Passages

**Exemplar 1: Quiet and intimate — father and son in the workshop**

> The workshop held its heat past dark. Cass sat on the cold stone bench
> by the door while his father worked at the lathe, turning a clapper
> for one of the lesser civic bells — the Seventh of Ash Street, the one
> that called the fish market closed.
>
> Metal dust drifted in the lamplight. The air tasted of linseed oil
> and old bronze.
>
> His father's hands moved with a sureness they didn't have at the
> dinner table. Here, among the bells, the tremor settled. Some nights
> you could almost forget it was there. Almost forget the sound of his
> voice thinning when Cass asked about Perin, about the contract, about
> why a brother could vanish into service and a father could keep eating
> his soup.
>
> "Hand me the pitch-gauge."
>
> Cass handed it over. Their fingers touched on the brass handle, and
> neither of them mentioned it.
>
> His father struck a test note. The clapper rang a clean B-flat
> against the practice bell — a tone so pure it made the oil jars hum
> in sympathy. For six seconds, the workshop was full of a sound that
> told no lies. Cass closed his eyes. Let it pool in his chest.
> Six seconds of silence from the frequency that hurt him.
>
> Then his father set the clapper down, and the silence was just
> silence again.

(This is the emotional core register. Restraint. Sensory specifics.
The unsaid thing louder than the spoken one. The body carrying the
feeling — closed eyes, the pooling in the chest. The six-second
reprieve structures the whole passage around a single clean note.)

**Exemplar 2: Tense and close — Cass hearing a lie in court**

> The defendant sang his oath in G-major, clean and formal, the way
> they teach you at the academy. Good breath support. Steady vibrato.
> His lawyer had coached him well.
>
> Cass heard the lie before the man finished the first phrase.
>
> It came in a key that had no name — a quarter-tone between F and
> F-sharp, a frequency that shouldn't exist in any scale the city
> recognized. His jaw tightened. A needle of pain slid behind his
> left eye and stayed there, hot and thin.
>
> The court singer nodded. The registrar recorded the oath as valid.
> Fourteen people in the gallery heard a man swear truthfully in
> G-major, and none of them flinched.
>
> Cass flinched.
>
> He pressed his tongue against the roof of his mouth, a trick his
> brother had taught him years ago. It didn't help. It never helped.
> But the pressure gave him something to do besides scream.
>
> The false note hung in the air like a smell no one else could
> detect. It had texture — greasy, curdled, wrong. Not the bright
> wrongness of a missed note. Something older. The sound of a mouth
> shaping words the throat wants to refuse.
>
> His hands were shaking. His father's hands did that too.

(This is the magic-system-in-action register. The technical music
vocabulary — G-major, quarter-tone, F-sharp — is used with the
fluency of someone trained in it. The pain is physical and specific:
needle behind the left eye, greasy texture. The one-line paragraph
"Cass flinched" does the structural work. The final line is a knife.)

**Exemplar 3: Lyrical and reflective — what music means in Cantamura**

> There is a pitch the body knows before the ear does.
>
> Cass had felt it first when he was small — five, maybe six — sitting
> beneath the Great Bell while his father tuned the resonance chamber.
> The whole building shook at a frequency below hearing, and something
> inside his ribcage answered. Not pain. Not pleasure. Recognition,
> like the pull of a word you've forgotten sitting just behind your
> teeth.
>
> Music in Cantamura was never about beauty. That was what outsiders
> got wrong. They visited and heard the song-brokers in the market,
> the courtroom choirs, the evening hymns rising from the temple steps,
> and they said: how beautiful, a city that sings. But beauty was a
> side effect. Music here was grammar. It was plumbing. It was the
> mechanism by which a city of ten thousand souls agreed on what was
> true and what was owed and who belonged to whom.
>
> And that was the part that broke his heart. Not that the music was
> used for law. He could accept that, the way you accept that fire
> cooks your dinner and also burns your hand. What broke him was that
> the music didn't care. A binding sung in perfect thirds bound the
> willing and the coerced with the same clean resonance. The intervals
> couldn't tell the difference.
>
> Only Cass could. And the intervals didn't ask his opinion.

(This is the philosophical register — the voice at its most expansive.
"Music here was grammar. It was plumbing." is the line that keeps it
from floating into abstraction. The fire metaphor is grounded and
domestic. The final line turns dry, almost funny, and that dryness
prevents self-pity. This passage states the novel's central theme
without announcing it.)

### Anti-Exemplars

**Anti-Exemplar 1: Too Precious — the voice treats Cantamura as
magical instead of lived-in**

> The morning light cascaded through the market like liquid gold, each
> sunbeam a note in nature's own great symphony, and Cass moved through
> it all like a dancer who has forgotten he is dancing. The coins sang
> their silver songs, and the song-brokers wove their melodic
> enchantments, and everything was music, music, always music — the
> eternal song of Cantamura, ancient and ever-new, a city that breathed
> in harmonies and exhaled in chords that shimmered with meaning beyond
> what words could capture.

(WRONG because: Every noun gets a musical metaphor. No grounding
detail — no seeds in the bread crust, no oil on a thumb, no specific
coin denomination. No humor. This voice treats Cantamura with awe,
but for Cass the music is as ordinary as plumbing. The stacked clauses
are rhythmically uniform. This is fantasy-voice-as-costume — all
surface shimmer, no grit underneath.)

**Anti-Exemplar 2: Too Modern / YA Quippy — the voice breaks the world**

> The courtroom was giving off seriously bad energy, and honestly? Cass
> was so over it. The guy on the stand was lying through his perfectly
> rehearsed oath, and Cass could literally hear the wrongness — this
> awful, nails-on-a-chalkboard frequency that made him want to crawl
> out of his own skull. But sure, let's all pretend the system works.
> That's cool. Everything's cool.

(WRONG because: Cantamura doesn't have "bad energy." The sarcasm is
all surface — Cass's humor is drier and more specific, born from
observation, not attitude. "Literally" and "so over it" shatter the
world's texture. This is a teen on social media, not a boy who grew
up tuning bells. The voice has no weight to it; when the story darkens,
this register has nowhere to go.)

**Anti-Exemplar 3: Too Epic / Grandiose — the voice inflates a family
story into prophecy**

> And so it was that Cassiel of the House of Bells, Second Son of the
> Bellwright Line, stood upon the threshold of a truth that would shake
> the very foundations of Cantamura itself. For the lie he had heard
> this day was no ordinary falsehood, but a crack in the great edifice
> of Tonal Law — a fissure through which the darkness would pour,
> unstoppable and all-consuming, until every bell in the city rang with
> the dissonance of a broken covenant.

(WRONG because: This is a family story, not a prophecy. Cass is
fourteen and confused, not standing on thresholds of truth. "Shake
the very foundations" is the kind of portentous throat-clearing that
makes fantasy exhausting. The danger in this novel is personal — a
brother lost, a father's cowardly silence, a boy in constant pain —
not apocalyptic. Full names and titles in narration create distance
where the voice needs closeness. If the prose sounds like it belongs
on a dust jacket, it doesn't belong in the chapter.)
