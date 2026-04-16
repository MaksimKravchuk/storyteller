"""Memory follow-up scenario — can Marcus recall facts from a prior scene?

The scenario seeds a :class:`GameState` with one NPC (Marcus the baker)
whose ``conversation_history`` + :class:`KnowledgeGraph` memory already
contain two facts from a previous scene: a loaf was stolen from his
stall yesterday, and he suspects a man named Gaius. The script then
asks Marcus to recall each fact on subsequent turns. The rubric checks
both the structured signal (``Marcus`` appears in dialogue) and the
LLM-judged semantic signal (his response references the prior facts).

The ``SCENARIO`` binding lives in
:mod:`benchmarks.scenarios.memory_follow_up_marcus._scenario`.
"""
