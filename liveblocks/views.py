from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse

User = get_user_model()

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_users_by_email_order(request):
    emails = request.data.get("emails")

    if not emails or not isinstance(emails, list):
        return JsonResponse({"error": "Provide a list of emails in 'emails'"}, status=400)

    # Fetch all users whose emails match the list
    users_qs = User.objects.filter(email__in=emails)
    users_map = {user.email: user for user in users_qs}

    result = []
    for email in emails:
        user = users_map.get(email)
        if user:
            result.append({
                "email": user.email,
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
            })
        else:
            result.append(None)

    return JsonResponse({"users": result})
