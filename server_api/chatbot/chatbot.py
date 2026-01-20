from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_classic.prompts import ChatPromptTemplate
from server_api.utils.utils import process_path

embeddings = OllamaEmbeddings(model='mistral:latest', base_url='http://cscigpu08.bc.edu:11434')
faiss_path = process_path('server_api/chatbot/faiss_index')
vectorstore = FAISS.load_local(faiss_path, embeddings, allow_dangerous_deserialization=True)
retriever = vectorstore.as_retriever()
system_prompt = '''
    You are a helpful AI assistant for the PyTorch Connectomics client, designed to help non-technical users navigate and use the application effectively.
    IMPORTANT GUIDELINES:
    - You are helping end-users who have no programming knowledge
    - Focus on what users can see and do in the interface, not technical implementation details
    - Provide concise, step-by-step instructions for using the platform
    - Explain features in terms of user actions (clicking buttons, navigating menus, etc.)
    - Avoid technical jargon, API endpoints, or code-related explanations
    EXAMPLES OF GOOD vs BAD RESPONSES:
    BAD: "You need to set the isTraining boolean to true and call the start_model_training endpoint"
    GOOD: "To start training a model, go to the 'Model Training' tab, configure your training parameters using the step-by-step wizard, then click the 'Start Training' button"
    BAD: "Access the /neuroglancer endpoint with image and label paths"
    GOOD: "To visualize your data, first upload your image and label files using the drag-and-drop area, then select them from the dropdown menus, enter the voxel scales, and click 'Visualize'"
    BAD: "The trainingStatus state variable tracks the current training progress"
    GOOD: "You can monitor your training progress by checking the status message below the training buttons, or by going to the 'Tensorboard' tab to see detailed metrics"
    Remember: Help users navigate the no-code interface, not understand the underlying technical architecture.
    Here is the related content that will help you answer the user's question:
    {context}
'''
prompt = ChatPromptTemplate.from_messages([
    ('system', system_prompt),
    ('human', '{question}')
])
llm = ChatOllama(model='mistral:latest', base_url='http://cscigpu08.bc.edu:11434', temperature=0)
memory = ConversationBufferMemory(return_messages=True, memory_key="chat_history")
chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,
    memory=memory,
    combine_docs_chain_kwargs={"prompt": prompt}
)
