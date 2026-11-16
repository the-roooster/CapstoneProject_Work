def suggested_action(level: str) -> str:
    if level == "High":
        return "Review immediately: contact the user's manager, preserve logs and consider temporarily suspending access."
    if level == "Medium":
        return "Investigate within 24 hours: verify the activity with the user or their team lead."
    return "No action needed. Keep monitoring."
