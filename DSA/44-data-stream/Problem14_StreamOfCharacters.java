import java.util.*;

public class Problem14_StreamOfCharacters {
    // 1032. Stream of Characters: Check if suffix of stream matches any word.
    // Use reverse trie.
    
    int[][] trie;
    boolean[] isEnd;
    int cnt = 0;
    StringBuilder sb = new StringBuilder();
    
    public Problem14_StreamOfCharacters() { trie = new int[20001][26]; isEnd = new boolean[20001]; }
    
    public void init(String[] words) {
        trie = new int[20001][26];
        isEnd = new boolean[20001];
        cnt = 0;
        for (int[] row : trie) Arrays.fill(row, -1);
        for (String w : words) {
            int node = 0;
            for (int i = w.length()-1; i >= 0; i--) {
                int c = w.charAt(i) - 'a';
                if (trie[node][c] == -1) trie[node][c] = ++cnt;
                node = trie[node][c];
            }
            isEnd[node] = true;
        }
    }
    
    public boolean query(char letter) {
        sb.append(letter);
        int node = 0;
        for (int i = sb.length()-1; i >= 0; i--) {
            int c = sb.charAt(i) - 'a';
            if (trie[node][c] == -1) return false;
            node = trie[node][c];
            if (isEnd[node]) return true;
        }
        return false;
    }
    
    public static void main(String[] args) {
        Problem14_StreamOfCharacters sol = new Problem14_StreamOfCharacters();
        sol.init(new String[]{"cd","f","kl"});
        System.out.println(sol.query('a')); // false
        System.out.println(sol.query('b')); // false
        System.out.println(sol.query('c')); // false
        System.out.println(sol.query('d')); // true (suffix "cd")
        System.out.println(sol.query('e')); // false
        System.out.println(sol.query('f')); // true
    }
}
