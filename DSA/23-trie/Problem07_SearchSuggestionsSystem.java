import java.util.*;

/**
 * Problem 7: Search Suggestions System
 * 
 * Given products array and a searchWord, after each character typed, suggest at most 3 products
 * that have the same prefix, sorted lexicographically.
 * 
 * Time Complexity: O(n*m*log(n) + s*3) where n=products, m=avg length, s=searchWord length
 * Space Complexity: O(n*m) for trie
 * 
 * Production Analogy: Amazon/Google search suggestions, IDE code completion dropdown,
 * e-commerce product search typeahead.
 */
public class Problem07_SearchSuggestionsSystem {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
        List<String> suggestions = new ArrayList<>(); // store top 3 at each node
    }

    public static List<List<String>> suggestedProducts(String[] products, String searchWord) {
        Arrays.sort(products);
        TrieNode root = new TrieNode();
        for (String p : products) {
            TrieNode node = root;
            for (char c : p.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null) node.children[idx] = new TrieNode();
                node = node.children[idx];
                if (node.suggestions.size() < 3) node.suggestions.add(p);
            }
        }

        List<List<String>> result = new ArrayList<>();
        TrieNode node = root;
        for (int i = 0; i < searchWord.length(); i++) {
            int idx = searchWord.charAt(i) - 'a';
            if (node != null) node = node.children[idx];
            result.add(node == null ? new ArrayList<>() : node.suggestions);
        }
        return result;
    }

    public static void main(String[] args) {
        String[] products = {"mobile","mouse","moneypot","monitor","mousepad"};
        System.out.println(suggestedProducts(products, "mouse"));
        // [[mobile,moneypot,monitor],[mobile,moneypot,monitor],[mouse,mousepad],[mouse,mousepad],[mouse,mousepad]]

        System.out.println(suggestedProducts(new String[]{"havana"}, "havana"));
        System.out.println(suggestedProducts(new String[]{"bags","baggage","banner","box","cloths"}, "bags"));
    }
}
