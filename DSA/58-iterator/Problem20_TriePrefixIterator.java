import java.util.*;

public class Problem20_TriePrefixIterator {
    static class TrieNode { TrieNode[] children = new TrieNode[26]; boolean isEnd; }

    TrieNode root = new TrieNode();

    void insert(String word) {
        TrieNode cur = root;
        for (char c : word.toCharArray()) {
            if (cur.children[c-'a'] == null) cur.children[c-'a'] = new TrieNode();
            cur = cur.children[c-'a'];
        }
        cur.isEnd = true;
    }

    // Iterator over all words with given prefix
    public Iterator<String> prefixIterator(String prefix) {
        List<String> words = new ArrayList<>();
        TrieNode node = root;
        for (char c : prefix.toCharArray()) {
            if (node.children[c-'a'] == null) return words.iterator();
            node = node.children[c-'a'];
        }
        collectWords(node, new StringBuilder(prefix), words);
        return words.iterator();
    }

    void collectWords(TrieNode node, StringBuilder sb, List<String> words) {
        if (node.isEnd) words.add(sb.toString());
        for (int i = 0; i < 26; i++) if (node.children[i] != null) {
            sb.append((char)('a'+i));
            collectWords(node.children[i], sb, words);
            sb.deleteCharAt(sb.length()-1);
        }
    }

    public static void main(String[] args) {
        Problem20_TriePrefixIterator trie = new Problem20_TriePrefixIterator();
        for (String w : new String[]{"apple","app","application","bat","ball"}) trie.insert(w);
        Iterator<String> it = trie.prefixIterator("app");
        while (it.hasNext()) System.out.println(it.next());
    }
}
