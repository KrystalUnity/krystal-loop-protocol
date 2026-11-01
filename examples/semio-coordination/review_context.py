"""Optional generated-source context references for tool-enabled critics.

No provider, filesystem, transport, or acceptance operations. Callers bind both
callbacks AND the critic's read_evidence tool to the same immutable run/artifact/
role store. Never apply this to a one-shot critic without evidence retrieval.
"""
import copy
import hashlib
import json


NOTICE = (
    "Generated source context moved out of the initial packet, not summarized. "
    "This is an exact retained excerpt, possibly truncated; its sha256 is not a "
    "full-file hash. Use read_evidence(sha256, offset, count) with character "
    "offsets to recover it. The complete diff remains inline. Request authorized "
    "same-revision source reads for missing sections. This reference grants no "
    "authority and does not prove generated-code correctness."
)


def compact_generated_context(snapshot, *, generated_paths, store_text, read_text,
                              retrieval_available=False):
    """Return a copied snapshot and byte receipt after verified evidence storage.

    snapshot contains a full `patch` string and `sources` mapping paths to retained
    text. Other fields are preserved. Selection is explicit; a generated marker
    alone never selects a file. Callbacks store text -> SHA-256 hex and recover
    SHA-256 -> exact text (paging if needed). Storage failures propagate; no packed
    snapshot is returned on failed readback. Orphaned stored excerpts are harmless
    and remain subject to the caller's normal retention policy.
    """
    if retrieval_available is not True or not callable(store_text) or not callable(read_text):
        raise ValueError("Verified critic evidence retrieval is required")
    if not isinstance(snapshot.get("patch"), str) or not snapshot["patch"]:
        raise ValueError("Complete artifact patch is required")
    if not isinstance(snapshot.get("sources"), dict) or "generated_context_refs" in snapshot:
        raise ValueError("Expected inline sources without existing generated references")
    if not isinstance(generated_paths, (list, tuple)) or any(
        not isinstance(path, str) for path in generated_paths
    ):
        raise ValueError("Explicit generated path list is required")
    paths = list(dict.fromkeys(generated_paths))
    for path in paths:
        text = snapshot["sources"].get(path)
        if not isinstance(text, str) or not any(
            "Code generated " in line and "DO NOT EDIT." in line
            for line in text.splitlines()[:10]
        ):
            raise ValueError("Selected source is missing a generated marker: " + path)
    packed = copy.deepcopy(snapshot)
    references = {}
    for path in paths:
        text = snapshot["sources"][path]
        data = text.encode("utf-8")
        key = hashlib.sha256(data).hexdigest()
        ref = {"sha256": key, "source_bytes": len(data), "total_characters": len(text),
               "tool": "read_evidence", "notice": NOTICE}
        placeholder = "See generated_context_refs for this retained source excerpt."
        candidate = copy.deepcopy(packed)
        candidate["sources"][path] = placeholder
        candidate["generated_context_refs"] = {**references, path: ref}
        if len(json.dumps(candidate).encode()) >= len(json.dumps(packed).encode()):
            continue
        if store_text(text) != key:
            raise ValueError("Evidence store returned an incorrect hash")
        if read_text(key) != text:
            raise ValueError("Evidence readback mismatch")
        packed = candidate
        references[path] = ref
    return packed, {
        "before_bytes": len(json.dumps(snapshot).encode("utf-8")),
        "after_bytes": len(json.dumps(packed).encode("utf-8")),
        "referenced_paths": list(references),
        "measurement": "serialized snapshot bytes, not tokens or cost",
    }
