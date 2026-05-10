# Data Cow - a real ai assistant 
## Components
The system is composed of  main components: 
1. Agent Orchestrator 
2. Inference Layer 
3. Data Layer 
4. Edge Device 
5. Web Frontend


the aim of this project is to have a truly smart and capable ai assistant that follows you during the day as a real-life assistant would. 

we have two separate data collection layers: 

1. Document Collection & Processing: 
we have a service that uses rclone that automatically syncs our remote documents to our local device, these documents then get locally parsed and embedded to be used by our agent. Since our model is small and our document load is big we have implemented a multi layer retreival process, where our agent first accesses a document catalogue which contains document uuids paired with a short summary and embedding of the summary of the said document. using this our model narrows its scope when doing a full chunk search improving its negative retention rates. The documents get parsed using docling locally then they get embedded using `text-embedding-embeddinggemma-300m` hosted on LMStudio. Our pipeline is capable of extracting both text and images from our files, so that these images can be used by the llm when producing outputs. 

2. Video Collection & Processing: 

we have an edge device in this case a smartphone which runs a flutter app which constantly records a video which gets periodically sent to our video collection module via a rest api endpoint which accepts mp4 files. These mp4 files pass through a 5 stage transformation process where they first get diarized using librosa then the diarised sections pass through a transcription and autoregressive feature extraction through the usage of a vlm in our specific case `gemma 4 e4b`. these features then get sent to a name entity extractor which creates calendar event drafts which have to be approved by the user. furthermore these transcriptions get stored in a separate vectordb collection which contains all the metadata extracted by the vlm, so that we can use the transcription data when interacting with our main 'assistant'. 

3. Inference Layer
Due to our intense usage of the vlm model we decided to use a small gemma 4 4b model for both the aformentioned pipeline and our main agent, the inference of the model and of the embedding model is done through lmstudio which runs on an ollama backend. our api is then exposed on 0.0.0.:1234/v1. we have decided to go agressive on the parallel instances and on the concurrently passed token size which is set to 1024 tokens, making our inference speed approximately 75tok/s 

4. Agent Layer
Our agents are exclusively set on Langchain using an orchestrator - subagent layout, this allows us to not over saturate our small models context window while making sure that the different instances of the model keep separate and specific contexts. 

our agents are as follows: 

document_agent - agent that does document and vector db retreivals
calendar_agent - agent that interacts with google cloud api 
orchestrator agent - agent that plans and manages the other agents. 


