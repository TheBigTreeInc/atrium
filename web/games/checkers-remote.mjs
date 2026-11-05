import {createHostedCheckersPlayer} from '../src/checkers_remote_entry.mjs';

const root=document.getElementById('checkersPlayer');
if(root)createHostedCheckersPlayer(root);
