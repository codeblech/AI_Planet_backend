import os
import google.generativeai as genai
import chromadb
from pypdf import PdfReader
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv
load_dotenv()


class PDFProcessor:
    """
    A service class for processing PDF documents and handling Q&A interactions.

    This class manages the integration with Google's Gemini AI and ChromaDB for
    document processing and question answering capabilities.

    Attributes:
        embedding_model (str): The name of the text embedding model
        llm (GenerativeModel): Instance of Gemini AI model
        chroma_client (chromadb.Client): ChromaDB client for vector storage
        collections (Dict[str, chromadb.Collection]): Dictionary of active collections
    """

    def __init__(self):
        # Initialize Gemini
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.embedding_model = "models/text-embedding-004"
        self.llm = genai.GenerativeModel("gemini-1.5-flash")
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.Client()
        
        self.collections: Dict[str, chromadb.Collection] = {}

    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF file"""
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()

    async def process_pdfs(self, session_id: str, pdf_paths: List[Path]) -> None:
        """
        Process multiple PDFs for a session and store their contents in ChromaDB.

        Args:
            session_id (str): Unique identifier for the session
            pdf_paths (List[Path]): List of paths to PDF files

        Returns:
            None
        """
        # Create a new collection for this session
        collection = self.chroma_client.create_collection(name=session_id)
        self.collections[session_id] = collection
        
        # Process each PDF
        for i, pdf_path in enumerate(pdf_paths):
            text = self._extract_text_from_pdf(pdf_path)
            
            # Add to ChromaDB with document ID based on file name
            collection.add(
                documents=[text],
                ids=[f"{session_id}_doc_{i}"]
            )

    async def get_answer(self, session_id: str, question: str) -> str:
        """
        Generate an answer for a question using the processed PDFs.

        Args:
            session_id (str): Session identifier to retrieve relevant documents
            question (str): User's question

        Returns:
            str: Generated answer based on the document context
        """
        if session_id not in self.collections:
            return "No documents found for this session. Please upload PDFs first."
        
        # Query the collection to get relevant context
        results = self.collections[session_id].query(
            query_texts=[question],
            n_results=2
        )
        
        # Combine relevant documents as context
        context = "\n".join(results['documents'][0])
        
        # Generate prompt for Gemini
        prompt = f"""Based on the following context, answer the question. 
        If the answer cannot be found in the context, say "I cannot find the answer in the provided documents."
        
        Context:
        {context}
        
        Question: {question}"""
        
        # Generate response using Gemini
        response = self.llm.generate_content(prompt)
        return response.text

    def cleanup_session(self, session_id: str) -> None:
        """Clean up resources for a session"""
        if session_id in self.collections:
            self.chroma_client.delete_collection(session_id)
            del self.collections[session_id]
