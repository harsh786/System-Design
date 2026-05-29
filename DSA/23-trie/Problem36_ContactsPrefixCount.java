/**
 * Problem 36: Contacts Prefix Count
 * 
 * Operations: add(name), find(prefix) -> return count of contacts with that prefix.
 * 
 * Time Complexity: O(m) per operation
 * Space Complexity: O(n*m)
 * 
 * Production Analogy: Social media friend suggestions, LinkedIn connection search,
 * contact management systems counting matches.
 */
public class Problem36_ContactsPrefixCount {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        int prefixCount = 0;
    }

    static class Contacts {
        TrieNode root = new TrieNode();

        void add(String name) {
            TrieNode node = root;
            for (char c : name.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
                node.prefixCount++;
            }
        }

        int find(String prefix) {
            TrieNode node = root;
            for (char c : prefix.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) return 0;
                node = node.children[idx];
            }
            return node.prefixCount;
        }
    }

    public static void main(String[] args) {
        Contacts contacts = new Contacts();
        contacts.add("hack");
        contacts.add("hackerrank");
        System.out.println(contacts.find("hac"));  // 2
        System.out.println(contacts.find("hak"));  // 0
        contacts.add("hackathon");
        System.out.println(contacts.find("hac"));  // 3
        System.out.println(contacts.find("hack")); // 3
        System.out.println(contacts.find("hacke"));// 1
    }
}
