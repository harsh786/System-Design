import java.util.*;

public class Problem36_WordSearchII {
    class TrieNode { TrieNode[] children = new TrieNode[26]; String word; }
    public List<String> findWords(char[][] board, String[] words) {
        TrieNode root = new TrieNode();
        for (String w : words) { TrieNode node = root; for (char c : w.toCharArray()) { if (node.children[c-'a']==null) node.children[c-'a']=new TrieNode(); node=node.children[c-'a']; } node.word=w; }
        List<String> result = new ArrayList<>();
        for (int i = 0; i < board.length; i++) for (int j = 0; j < board[0].length; j++) dfs(board,i,j,root,result);
        return result;
    }
    private void dfs(char[][] board, int r, int c, TrieNode node, List<String> result) {
        if (r<0||r>=board.length||c<0||c>=board[0].length||board[r][c]=='#') return;
        char ch = board[r][c]; TrieNode next = node.children[ch-'a'];
        if (next == null) return;
        if (next.word != null) { result.add(next.word); next.word=null; }
        board[r][c]='#'; dfs(board,r+1,c,next,result); dfs(board,r-1,c,next,result); dfs(board,r,c+1,next,result); dfs(board,r,c-1,next,result); board[r][c]=ch;
    }
    public static void main(String[] args) { System.out.println(new Problem36_WordSearchII().findWords(new char[][]{{'o','a','a','n'},{'e','t','a','e'},{'i','h','k','r'},{'i','f','l','v'}}, new String[]{"oath","pea","eat","rain"})); }
}
