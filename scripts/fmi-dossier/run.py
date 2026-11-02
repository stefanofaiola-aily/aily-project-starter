"""Thin script alias for the independently registered dossier CLI task."""

from aily_project.services.fmi_dossier.runner import fmi_dossier

if __name__ == "__main__":
    fmi_dossier()
