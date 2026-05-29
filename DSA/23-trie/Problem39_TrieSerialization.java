import java.util.*;

/**
 * Problem 39: Trie Serialization and Deserialization
 * 
 * Serialize trie to string and reconstruct it. Useful for persistence/network transfer.
 * 
 * Time Complexity: O(n) for both serialize and deserialize where n = total nodes
 * Space Complexity: O(n)
 * 
 * Production Analogy: Saving autocomplete index to disk, transferring routing tables
 * between routers, caching trie structures in Redis, distributing dictionaries.
 */
public class Problem39_TrieSerialization {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    static class TrieCodec {
        // Format: char(isEnd:0/1){children}
        // Example: "a1{b0{c1{}}}" for word "abc" where 'a' not end, 'b' not end, 'c' is end

        String serialize(TrieNode root) {
            StringBuilder sb = new StringBuilder();
            serializeHelper(root, sb);
            return sb.toString();
        }

        void serializeHelper(TrieNode node, StringBuilder sb) {
            sb.append(node.isEnd ? '1' : '0');
            for (int i = 0; i < 26; i++) {
                if (node.children[i] != null) {
                    sb.append((char)('a' + i));
                    serializeHelper(node.children[i], sb);
                }
            }
            sb.append('#'); // end of children marker
        }

        TrieNode deserialize(String data) {
            int[] idx = {0};
            return deserializeHelper(data, idx);
        }

        TrieNode deserializeHelper(String data, int[] idx) {
            TrieNode node = new TrieNode();
            node.isEnd = data.charAt(idx[0]++) == '1';
            while (idx[0] < data.length() && data.charAt(idx[0]) != '#') {
                int childIdx = data.charAt(idx[0]++) - 'a';
                node.children[childIdx] = deserializeHelper(data, idx);
            }
            idx[0]++; // skip '#'
            return node;
        }
    }

    static boolean search(TrieNode root, String word) {
        TrieNode node = root;
        for (char c : word.toCharArray()) {
            if (node.children[c - 'a'] == null) return false;
            node = node.children[c - 'a'];
        }
        return node.isEnd;
    }

    public static void main(String[] args) {
        TrieNode root = new TrieNode();
        // Build trie
        for (String w : new String[]{"apple", "app", "bat"}) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
        }

        TrieCodec codec = new TrieCodec();
        String serialized = codec.serialize(root);
        System.out.println("Serialized: " + serialized);

        TrieNode deserialized = codec.deserialize(serialized);
        System.out.println(search(deserialized, "apple")); // true
        System.out.println(search(deserialized, "app"));   // true
        System.out.println(search(deserialized, "bat"));   // true
        System.out.println(search(deserialized, "ba"));    // false
        System.out.println(search(deserialized, "cap"));   // false
    }
}
