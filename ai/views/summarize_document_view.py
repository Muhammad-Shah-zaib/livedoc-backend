# views.py
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import google.generativeai as genai

class SummarizeDocumentView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        content = request.data.get("content")
        if not content:
            return Response({"error": "No content provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"Summarize the following text:\n\n{content}"
            response = model.generate_content(prompt)
            return Response({"summary": response.text.strip()}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
