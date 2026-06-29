# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Tool-code for switching workspace tabs by space-type.
"""

__all__ = (
    "Params",
    "Result",
    "main",
)

from typing import NamedTuple


class Params(NamedTuple):
    space_type: str
    allow_edits: bool


class Result(NamedTuple):
    status: str
    workspace: str | None = None
    space_type: str | None = None
    created: bool | None = None
    message: str | None = None
    available_space_types: list[str] | None = None


def main(params: Params) -> Result:
    import bpy  # pylint: disable=import-error,no-name-in-module

    if bpy.app.background:
        return Result(status="error", message="Not available in background mode")
    if bpy.context.window is None:
        return Result(status="error", message="No active window")

    requested = params.space_type

    def _largest_area(screen: "bpy.types.Screen") -> "bpy.types.Area | None":
        return max(screen.areas, key=lambda a: a.width * a.height, default=None)

    # An Area can be addressed by two vocabularies, and we accept either:
    #   * `area.type`    - coarse editor type (VIEW_3D, NODE_EDITOR, IMAGE_EDITOR, ...).
    #   * `area.ui_type` - fine-grained variant (ShaderNodeTree, CompositorNodeTree, UV, ...),
    #                      the same vocabulary the screenshot tool's `area_ui_type` accepts.
    # `ui_type` is a *dynamic* enum (its valid values depend on the area), so we cannot
    # validate it from a static enum list. Instead, match against both attributes, and when
    # editing, attempt to assign each attribute under try/except so an unsupported value
    # returns a structured error instead of a raw traceback.
    def _matches(area: "bpy.types.Area | None") -> bool:
        return area is not None and (area.type == requested or area.ui_type == requested)

    def _open_area_kinds() -> list[str]:
        kinds: set[str] = set()
        for ws in bpy.data.workspaces:
            for screen in ws.screens:
                area = _largest_area(screen)
                if area is not None:
                    kinds.add(area.type)
                    kinds.add(area.ui_type)
        return sorted(kinds)

    # Find an existing workspace whose largest area already matches.
    found = None
    for ws in bpy.data.workspaces:
        for screen in ws.screens:
            if _matches(_largest_area(screen)):
                found = ws
                break
        if found:
            break

    if found:
        bpy.context.window.workspace = found
        return Result(status="ok", workspace=found.name, space_type=requested)

    if params.allow_edits:
        # Duplicate the current workspace and retype its main area.
        try:
            bpy.ops.workspace.duplicate()
        except RuntimeError as ex:
            return Result(status="error", message=str(ex))
        new_ws = bpy.context.window.workspace
        area = _largest_area(bpy.context.screen)
        if area is not None:
            last_err: Exception | None = None
            for attr in ("ui_type", "type"):
                try:
                    setattr(area, attr, requested)
                    last_err = None
                    break
                except (TypeError, ValueError) as ex:
                    last_err = ex
            if last_err is not None:
                # Roll back the workspace we just created, then report cleanly.
                try:
                    bpy.ops.workspace.delete()
                except RuntimeError:
                    pass
                return Result(
                    status="error",
                    message="Unknown or unsupported space type {!r}: {:s}".format(requested, str(last_err)),
                    available_space_types=_open_area_kinds(),
                )
        new_ws.name = requested.replace("_", " ").title()
        return Result(
            status="ok",
            workspace=new_ws.name,
            space_type=requested,
            created=True,
        )

    return Result(
        status="error",
        message="No workspace with space type {!r} found (set allow_edits=True to create one)".format(requested),
        available_space_types=_open_area_kinds(),
    )
