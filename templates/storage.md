see https://console.firebase.google.com/u/0/project/arxiv-website/storage/arxiv-website.appspot.com/files

idea is that records stored as json files to run queries against since firebase is noSQL.

- paper_info contains the paper's idetifier, information, and category to send to mods
- mod_queues maps from mod categories to which paper ids are in the queue
- mod_results is what moderators return after labeling the paper: the paper id and corresponding answer of whether it fits in this category
