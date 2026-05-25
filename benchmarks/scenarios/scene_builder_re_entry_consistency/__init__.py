"""SceneBuilder consistency when the player leaves and returns to a location.

Drives the player out of the Forum Romanum onto a side street, then
back to the Forum, and measures whether the second SceneBuilder pass
preserves the landmarks the first pass anchored — the rebuild must
not rename ``Temple of Saturn`` into ``Temple of Jupiter``, drop the
``rostra``, or duplicate any POI on re-entry.
"""
