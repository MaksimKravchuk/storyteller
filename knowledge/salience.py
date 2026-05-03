"""Salience presets for newly-created memories.

Every call site that builds a ``PERSONAL_EXPERIENCE`` node should reach
into this module rather than hard-coding a literal so the tuning can be
revisited in one place. Higher values keep a memory near the top of an
NPC's recall set for longer; see ``KnowledgeQueryEngine.get_memories_held_by``
for the salience+recency blend.

Numbers are deliberately spread across the 0.0–1.0 scale so the
weighted score in the query engine has enough dynamic range to flip a
pivotal-but-stale event past a routine-but-fresh one.
"""

from __future__ import annotations

# Routine first-person dialogue summaries. Most NPC interactions are
# small-talk and should not crowd out witnessed events of consequence.
ROUTINE_DIALOGUE = 0.4

# Co-witness "I overheard" memories. The bystander doesn't own the
# exchange, so it ranks below the targeted dialogue summary above.
OVERHEARD = 0.3

# Object interactions persisted as scene-state memories. A door kicked in
# matters more than chatter but less than physical clashes.
OBJECT_INTERACTION = 0.5

# Witnessed combat — the canonical high-salience event class.
COMBAT = 0.85

# Retaliation summaries are combat by another name — an NPC's mood
# flipped into an attack, so weight them with the same gravity.
RETALIATION = 0.85

# Remote/scheduled events that finish off-camera. They land as rumours
# / fact nodes for non-witnesses and personal memories for witnesses;
# both deserve more weight than chitchat but less than a clash you saw.
REMOTE_EVENT = 0.6

# Neutral midpoint; used only when a caller can't classify the event.
DEFAULT = 0.5
