import java.util.*;

/**
 * Problem 35: Phone Directory Prefix Search
 * 
 * Given a list of contacts, for each prefix typed on a phone keypad,
 * return all matching contacts.
 * 
 * Time Complexity: O(n*m) build, O(prefix + results) per query
 * Space Complexity: O(n*m)
 * 
 * Production Analogy: Phone contact search (iOS/Android dialer), T9 predictive text,
 * CRM customer lookup, address book search.
 */
public class Problem35_PhoneDirectoryPrefixSearch {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        List<String> contacts = new ArrayList<>();
    }

    static class PhoneDirectory {
        TrieNode root = new TrieNode();

        void addContact(String name) {
            String lower = name.toLowerCase();
            TrieNode node = root;
            for (char c : lower.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
                node.contacts.add(name);
            }
        }

        List<String> search(String prefix) {
            TrieNode node = root;
            for (char c : prefix.toLowerCase().toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) return new ArrayList<>();
                node = node.children[idx];
            }
            return node.contacts;
        }
    }

    public static void main(String[] args) {
        PhoneDirectory dir = new PhoneDirectory();
        dir.addContact("Alice");
        dir.addContact("Bob");
        dir.addContact("Albert");
        dir.addContact("Alex");
        dir.addContact("Bobby");

        System.out.println(dir.search("al"));  // [Alice, Albert, Alex]
        System.out.println(dir.search("b"));   // [Bob, Bobby]
        System.out.println(dir.search("bo"));  // [Bob, Bobby]
        System.out.println(dir.search("c"));   // []
        System.out.println(dir.search("ali")); // [Alice]
    }
}
