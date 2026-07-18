from .models import Branch


def current_branch(request):
    """Makes the current_branch available in all templates."""
    branch_id = request.session.get("current_branch_id")
    if branch_id:
        try:
            branch = Branch.objects.get(pk=branch_id, is_active=True)
            return {"current_branch": branch}
        except Branch.DoesNotExist:
            pass
    return {"current_branch": None}
