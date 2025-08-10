import google.generativeai as genai
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.shortcuts import get_object_or_404
from document.models import Document, LiveDocumentUser


class SummarizeDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    # Class-level variables initialized only once when the class is loaded
    _model_initialized = False

    @classmethod
    def initialize_model(cls):
        if not cls._model_initialized:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            cls.model = genai.GenerativeModel("gemini-1.5-flash")
            cls._model_initialized = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize the model when the view is first instantiated
        self.initialize_model()

    def patch(self, request, id):
        # Get the document or return 404 if not found
        document = get_object_or_404(Document, id=id)
        is_user_in_room = LiveDocumentUser.objects.filter(
            document=document,
            user=request.user
        ).exists()

        if not is_user_in_room:
            return Response({"detail": "You do not have access to this document."},
                            status=status.HTTP_403_FORBIDDEN)

        content = request.data.get("content", "").strip()
        if not content:
            return Response({"detail": "No content is provided for summary to summarize."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            # Use the pre-initialized model
            prompt = f"Summarize the following text:\n\n{content}"
            response = self.__class__.model.generate_content(prompt)
            summary = response.text.strip()

            # Update and save the document with the summary
            document.content = content
            document.summary = summary
            document.save()

            return Response({
                "summary": summary,
                "detail": "Document summary saved successfully."
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
