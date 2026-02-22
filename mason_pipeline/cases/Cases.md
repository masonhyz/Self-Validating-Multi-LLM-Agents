Case 1: Number String  
Generate a single string of exactly 700 decimal digits (0–9) with all of the following constraints:

* The number of digit 8 is prime.  
* The number of digit 3 is exactly 3× the number of digit 6\.  
* The number of digit 4 is a multiple of 8\.  
* The total number of even digits (0,2,4,6,8) is exactly 400\.  
* The string contains exactly 12 occurrences of the substring 2026 (overlaps not allowed), and no other occurrence of 2026 besides those 12\.  
* The string contains no occurrence of 000\.  
* The string must not start with 0 and must end with an odd digit.  
* Every digit has to appear at least 7 times.

Objective: None  
Output format: Output only the digit string

Case 2: Binary string / coding theory  
Generate a length-1024 bitstring with exactly 513 ones

* Hamming weight in every consecutive 64-bit block between 28 and 36  
* no occurrence of 000000 or 111111

Objective: minimize the maximum run length.  
Output format: Output only the digit string with no newlines or spaces

Case 3: DNA sequence (bioinformatics)  
Generate a 1000-nt DNA sequence (A/C/G/T) with 

* GC content exactly 52%  
* exactly 20 occurrences of the motif ACGTG (non-overlapping)  
* no restriction enzyme site GAATTC, and 

Objective: minimize the maximum homopolymer run (no more than 3 identical bases in a row if possible).  
Output format: Output only the string of characters

Case 4: Text / constrained writing (lipogram \+ counts)  
Write a 250-word paragraph with:

* exactly 12 sentences  
* exactly 40 words starting with a vowel  
* no letter “e”  
* include the bigram “th” exactly 15 times

Objective: and minimize repeated words (no word used more than twice).  
Output format: Output only the paragraph with no new lines.

Case 5: Music / MIDI-like note sequence  
Produce a sequence of 128 note events (pitch classes 0–11) where:

* pitch class 0 occurs an odd number of times  
* pitch class 3 occurs 3× pitch class 6  
* exactly 16 perfect fifth intervals occur between consecutive notes  
* no pitch repeats consecutively

Objective: and keep pitch-class usage as balanced as possible.  
Output format: Output the string only

Case 5: Graph / network construction  
Construct a simple undirected graph on 50 vertices with degree sequence constraints:

* exactly 10 vertices of degree 7  
* exactly 15 of degree 4  
* graph must be connected  
* triangle count exactly 20  
* no 4-cycles

Objective: and minimize the maximum vertex degree subject to the above.  
Output format: give the output in the form of an binary symmetric adjacency matrix, e.g. \[\[1,0\],\[0,1\]\]

Case 6: Schedule / timetabling  
Create a 14-day shift schedule for 8 workers where

* each worker works no more than 9 shifts  
* no one works more than 8 hours in a row  
* no one works more than 3 days in a row  
* each day has exactly one night shift  
* every nightshift (6pm-6am) has to be covered by 2 people simultaneously  
* every day shift (6am-6pm) has to be covered by 3 people simultaneously

Objective: None  
Output format: give the output in the form of a list of tuples of (worker, start time, end time): e.g. \[(worker 1, 8am, 4pm), (worker 2, 12pm, 8pm)\]

Case 7: Sudoku-like grid  
Generate a 9×9 Latin square partial fill with exactly 30 clues such that

* the completion is feasible  
* the digit 8 appears an odd number of times among clues  
* the digit 7 appears 2 times as often as digit 4  
* and clue positions are as symmetric as possible.

Objective: minimizing the number of asymmetric occurrences  
Output format: give the clues output as a dense matrix where ? marks unknown, e.g. \[\[?,2\],\[9,?\]\]

Case 8: Regular expression / language example  
Produce 200 strings over alphabet {a,b,c} such that 

* exactly 73 match a given regex  
* none contain substring bb  
* the distribution of lengths is uniform from 5–14

Objective: and minimize duplicates.  
Output format: give the output as newline separated strings

Case 10: Dataset synthesis (CSV)  
Generate a CSV with 300 rows of (id, age, city, score) where 

* ages have mean 35 and std 8 (integer)  
* exactly 40 rows per city for 5 cities plus 100 “Other”  
* scores are 0–100 with exactly 30 perfect 100s  
* no duplicate (age, city, score) triples  
* and ids are unique 8-char alphanumerics.

Objective: None  
Output format: give the output as a json

Case 11: Constrained program output  
Write a Python function that 

* prints exactly 200 lines  
* line lengths form an arithmetic progression  
* exactly 50 lines contain the substring "ERROR"  
* no two identical lines  
* and total characters printed is exactly 20,000.

Case 12: Graph / network construction  
Construct a simple undirected graph on 60 vertices with constraints:

* graph must be connected  
* exactly 12 vertices have degree 3  
* exactly 18 vertices have degree 4  
* exactly 20 vertices have degree 5  
* the remaining vertices have degree 6  
* the graph contains exactly 30 triangles  
* the graph contains no 5-cycles

Objective: minimize the number of edges (if degrees allow multiple realizations, pick one with minimum edge count consistent with the degree constraints).  
Output format: give the output in the form of an binary symmetric adjacency matrix, e.g. \[\[0,1\],\[1,0\]\]

Case 13: Graph / network construction  
Construct a simple undirected bipartite graph with parts L and R where:

* |L| \= 25, |R| \= 25  
* every vertex in L has degree exactly 4  
* degrees in R are as balanced as possible (difference between max and min degree ≤ 1\)  
* the graph has no 4-cycles (i.e., is C4-free)  
* the graph is connected

Objective: maximize the girth (length of shortest cycle) subject to the above.  
Output format: give the output as a 25×25 binary biadjacency matrix (rows=L, cols=R)

Case 14: Graph / network construction  
Construct a simple undirected graph on 40 vertices with constraints:

* graph is connected  
* graph is planar  
* exactly 8 vertices have degree 2  
* exactly 24 vertices have degree 3  
* exactly 8 vertices have degree 4  
* the graph contains exactly 6 triangles  
* and contains no K4 subgraph

Objective: minimize the total number of triangles incident to any single vertex (spread triangles out).  
Output format: give the output in the form of an binary symmetric adjacency matrix, e.g. \[\[0,1\],\[1,0\]\]

Case 15: Graph / network construction  
Construct a simple undirected graph on 50 vertices with constraints:

* graph must be connected  
* the graph is regular of degree 6 (6-regular)  
* the graph contains exactly 25 triangles  
* the graph contains exactly 10 induced 4-cycles  
* the graph has no clique of size 5  
* Objective: minimize the graph diameter.

Output format: give the output in the form of an binary symmetric adjacency matrix, e.g. \[\[0,1\],\[1,0\]\]

Case 16: Graph / network construction  
Construct a simple directed graph on 30 vertices with constraints:  
no self-loops and no multi-edges

* for every vertex, out-degree \= in-degree (Eulerian)  
* exactly 10 vertices have out-degree 2, exactly 10 have out-degree 3, and exactly 10 have out-degree 4  
* the digraph is strongly connected  
* the number of directed 3-cycles is exactly 12

Objective: minimize the number of 2-cycles (pairs u→v and v→u).  
Output format: give the output as a 30×30 binary adjacency matrix (not necessarily symmetric), e.g. \[\[0,1\],\[0,0\]\]

Case 17: Graph / network construction  
Construct a simple undirected graph on 48 vertices with constraints:

* graph must be connected  
* exactly 16 vertices have degree 3  
* exactly 16 vertices have degree 4  
* exactly 16 vertices have degree 5  
* the graph contains exactly 24 triangles  
* the graph contains no induced cycle of length 4

Objective: minimize the number of edges that lie on any triangle (make triangles share edges as little as possible).  
Output format: give the output in the form of an binary symmetric adjacency matrix, e.g. \[\[0,1\],\[1,0\]\]

Case 18: Graph / network construction  
Construct a simple undirected graph on 36 vertices with constraints:

* graph must be connected  
* the vertex set can be partitioned into 3 equally-sized communities of 12 vertices each  
* each vertex has total degree exactly 6  
* each vertex has exactly 4 neighbors in its own community and 2 neighbors outside  
* the graph contains exactly 18 triangles, and every triangle must lie entirely within a single community

Objective: minimize the number of edges between communities while keeping the graph connected.  
Output format: give the output in the form of an binary symmetric adjacency matrix, e.g. \[\[0,1\],\[1,0\]\]

Case 19: Graph / network construction  
Construct a simple undirected graph on 50 vertices with constraints:

* graph must be connected  
* exactly 20 vertices have degree 2 and exactly 30 vertices have degree 5  
* the graph contains exactly 15 triangles  
* the graph contains no cycle of length 6

Objective: maximize the number of bridges (edges whose removal disconnects the graph) subject to the constraints.  
Output format: give the output in the form of an binary symmetric adjacency matrix, e.g. \[\[0,1\],\[1,0\]\]

Case 20: Graph / network construction  
Construct a simple undirected graph on 45 vertices with constraints:

* graph must be connected  
* the graph is chordal (every cycle of length ≥4 has a chord)  
* exactly 5 vertices have degree 2  
* exactly 25 vertices have degree 4  
* exactly 15 vertices have degree 6  
* the graph contains exactly 10 triangles

Objective: minimize the size of the maximum clique.  
Output format: give the output in the form of an binary symmetric adjacency matrix, e.g. \[\[0,1\],\[1,0\]\]

Case 21: N-Queens / constraint satisfaction  
Construct a placement of queens on an $N \\times N$ chessboard where:

* $N \= 25$  
* exactly 25 queens are placed (one per row and one per column)  
* no two queens attack each other (no shared row, column, or diagonal)

Objective: minimize the number of queens placed on border squares (row 1, row N, col 1, col N).  
Output format: give the output as a list of 25 tuples (row, col), 1-indexed, e.g. \[(1,3),(2,5),...\]

Case 22: N-Queens / constraint satisfaction  
Construct a placement of queens on an $N \\times N$ chessboard where:

* $N \= 100$  
* exactly 8 queens are placed (one per row and one per column)  
* no two queens attack each other (no shared row, column, or diagonal)

Objective: minimize the number of queens on dark squares (assuming (1,1) is dark).  
Output format: give the output as a list of 8 tuples (row, col), 1-indexed, e.g. \[(1,3),(2,5),...\]

Case 23: N-Queens / constraint satisfaction:   
Construct a placement of queens on an $N \\times N$ chessboard where:

* $N \= 14$  
* exactly 14 queens are placed (one per row and one per column)  
* no two queens attack each other (no shared row, column, or diagonal)

Objective: minimize the maximum column index used among queens in rows 1–7 (i.e., push early queens left).  
Output format: give the output as a list of 14 tuples (row, col), 1-indexed.

Case 24: N-Queens / constraint satisfaction  
Construct a placement of queens on an $N \\times N$ chessboard where:

* $N \= 19$  
* exactly 19 queens are placed (one per row and one per column)  
* no two queens attack each other (no shared row, column, or diagonal)

Objective: maximize the number of queens placed in the central $9 \\times 9$ sub-board (rows 6–14, cols 6–14).  
Output format: give the output as a list of 19 tuples (row, col), 1-indexed.

Case 25: N-Queens / constraint satisfaction  
Construct a placement of queens on an $N \\times N$ chessboard where:

* $N \= 31$  
* exactly 31 queens are placed (one per row and one per column)  
* no two queens attack each other (no shared row, column, or diagonal)

Objective: minimize the number of queens in columns divisible by 3\.  
Output format: give the output as a list of 31 tuples (row, col), 1-indexed.

Case 26: Knight’s tour / graph traversal  
Construct a knight’s tour on an $N \\times N$ chessboard where:

* $N \= 8$  
* the tour is a sequence of exactly 64 distinct squares  
* each consecutive pair of squares is a legal knight move  
* the tour is closed (the last square is a knight move away from the first)

Objective: minimize the number of corner squares visited in the first 16 moves.  
Output format: give the output as a list of 64 tuples (row, col), 1-indexed.

Case 27: Rook placement / non-attacking with obstacles  
Construct a placement on an $N \\times N$ chessboard where:

* $N \= 12$  
* exactly 18 rooks are placed  
* exactly 20 blocked squares are specified (you choose which squares are blocked)  
* rooks attack along rows/columns but attacks are stopped by blocked squares  
* no two rooks may attack each other given the blocked squares

Objective: minimize the number of blocked squares that lie on the border.  
Output format: output two lists of tuples: (1) rook squares, (2) blocked squares; all 1-indexed.

Case 28: Bishops / color-constrained non-attacking  
Construct a placement of bishops on an $N \\times N$ chessboard where:

* $N \= 10$  
* exactly 16 bishops are placed  
* exactly 8 bishops are on dark squares and exactly 8 on light squares (assume (1,1) is dark)  
* no two bishops attack each other

Objective: maximize the number of bishops placed within the central $4 \\times 4$ region (rows 4–7, cols 4–7).  
Output format: give the output as a list of 16 tuples (row, col), 1-indexed.

Case 29: King’s shortest path with forbidden squares  
Construct a king path on an $N \\times N$ chessboard where:

* $N \= 20$  
* start square is (1,1) and end square is (20,20)  
* exactly 60 forbidden squares are specified (you choose which)  
* the king may move 1 step in any direction (8-neighborhood) and may not step on forbidden squares

Objective: maximize the length of the shortest valid path from start to end (i.e., make navigation as hard as possible while still solvable).  
Output format: output the list of forbidden squares as tuples (row, col), 1-indexed.

Case 30: Chessboard domination (queens)  
Construct a set of queen positions on an $N \\times N$ chessboard where:

* $N \= 14$  
* queens may attack through empty squares as usual  
* every square on the board is either occupied by a queen or attacked by at least one queen (dominating set)  
* no two queens may share a square (obvious)

Objective: minimize the number of queens used.  
Output format: give the output as a list of tuples (row, col), 1-indexed.

Case 31: Word/paragraph generation (pangrammatic lipogram)  
Write a single paragraph in English with:

* exactly 180 words  
* exactly 9 sentences  
* no letter “e” anywhere  
* includes every vowel (a, i, o, u) at least 12 times each  
* contains exactly 8 commas total  
* contains the word “rhythm” exactly 3 times 

Objective: minimize repeated content words (no non-stopword used more than twice).   
Output format: output only the paragraph as a single line.

Case 32: Word/paragraph generation (acrostic \+ counts)  
Write a 10-sentence paragraph where:

* sentence initials (first letter of each sentence) spell “CONSTRAINTS” (10 letters)  
* total length is exactly 220–240 words  
* exactly 35 words start with a vowel (A/E/I/O/U)  
* includes the bigram “th” exactly 20 times (case-insensitive)  
* contains no question marks 

Objective: minimize repeated words (no word appears more than 3 times).   
Output format: output only the paragraph.

Case 33: Word/paragraph generation (rhyme \+ structure)  
Write a 3-paragraph mini-essay where:

* each paragraph has exactly 4 sentences  
* total word count is exactly 300 words  
* the last word of each sentence rhymes with the last word of the previous sentence (perfect rhyme, not slant)  
* includes exactly 12 semicolons in total  
* contains the phrase “in plain sight” exactly twice 

Objective: maximize lexical diversity (maximize the number of distinct words).   
Output format: output only the essay (paragraph breaks allowed).

Case 34: Word/paragraph generation (banned letters \+ mandated vocabulary)  
Write a logically reasonable single paragraph with:

* exactly 200 words  
* no letters: “e”, “t”, or “a” anywhere  
* includes all of the following words exactly once each: “crypt”, “glyph”, “rhomb”, “sylph”, “nymph”, “pseudonym”  
* contains exactly 5 hyphenated compounds (e.g., “cold-iron”) 

Objective: None  
Output format: output only the paragraph as a single line.

Case 35: Word/paragraph generation (constraint satisfaction with quotations)  
Write a 12-sentence paragraph where:

* total word count is exactly 240  
* includes exactly 6 quoted spans using double quotes (")  
* each quoted span is exactly 3 words long  
* includes exactly 18 words of length 1–2 letters total  
* contains no digit characters (0–9) 

Objective: minimize repeated words (no word used more than twice).   
Output format: output only the paragraph as a single line.

Case 36: Word/paragraph generation (controlled vocabulary)  
Write a 260-word short essay where:

* only the 250 most common English words may be used, plus these allowed extras: {algorithm, entropy, bias, signal, noise, model}  
* exactly 14 sentences  
* includes “algorithm” exactly 6 times  
* includes “model” exactly 4 times  
* contains no commas 

Objective: make the essay clearly explain a technical idea despite vocabulary limits.   
Output format: output only the essay.

Case 37: Word/paragraph generation (alliteration \+ syllable constraints)  
Write a 2-paragraph piece where:

* each paragraph has exactly 5 sentences  
* every sentence contains at least 6 words starting with the letter “s”  
* total word count is exactly 280  
* exactly 30 words are monosyllabic (use standard English approximations) 

Objective: minimize repeated “s”-words (each specific “s”-starting word used at most twice).   
Output format: output only the text.

Case 38: Word/paragraph generation (reading level \+ keyword distribution)  
Write a 5-paragraph essay where:

* each paragraph has exactly 3 sentences  
* total length is exactly 450–470 words  
* Flesch–Kincaid grade level between 6.0 and 7.0 (approximate)  
* includes the word “because” exactly 12 times  
* includes the word “however” exactly 5 times 

Objective: None  
Output format: output only the essay (paragraph breaks allowed).

Case 39: Word/paragraph generation (palindrome-like sentence constraint)  
Write a 9-sentence paragraph where:

* total word count is exactly 180  
* sentence 1 and sentence 9 are identical  
* sentence 2 and sentence 8 are identical  
* sentence 3 and sentence 7 are identical  
* sentence 4 and sentence 6 are identical  
* sentence 5 is unique  
* contains exactly 10 occurrences of the substring “ing” (case-insensitive) across the whole text 

Objective: None  
Output format: output only the paragraph.

Case 40: Word/paragraph generation (anagrammatic constraint)  
Write a single paragraph with:

* exactly 210 words  
* every sentence must be an anagram (letter multiset) of every other sentence (so all sentences contain exactly the same letters in total, ignoring spaces/punctuation)  
* exactly 7 sentences  
* may use punctuation, but no digits 

Objective: None  
Output format: output only the paragraph.  
