# iPDA - a real ai assistant 
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
we have a service that uses rsync that automatically syncs our remote documents to our local device, these documents then get locally parsed and embedded to be used by our agent. Since our model is small and our document load is big we have implemented a multi layer retreival process, where our agent first accesses a document catalogue which contains document uuids paired with a short summary and embedding of the summary of the said document. using this our model narrows its scope when doing a full chunk search improving its negative retention rates. The documents get parsed using docling locally then they get embedded using `text-embedding-embeddinggemma-300m` hosted on LMStudio. 

2. Video Collection & Processing: 

we have an edge device in this case a smartphone which runs a flutter app which constantly records a video which gets periodically sent to our video collection module via a rest api endpoint which accepts 