import java.util.*;

public class Problem46_TreapOperations {
    static Random rand = new Random();
    static class Node { int key,pri,size; Node l,r; Node(int k){key=k;pri=rand.nextInt();size=1;} }

    static int size(Node n){return n==null?0:n.size;}
    static void update(Node n){if(n!=null)n.size=1+size(n.l)+size(n.r);}

    static Node[] split(Node t, int key) {
        if(t==null) return new Node[]{null,null};
        if(key<=t.key){Node[] s=split(t.l,key);t.l=s[1];update(t);return new Node[]{s[0],t};}
        else{Node[] s=split(t.r,key);t.r=s[0];update(t);return new Node[]{t,s[1]};}
    }

    static Node merge(Node l, Node r) {
        if(l==null)return r; if(r==null)return l;
        if(l.pri>r.pri){l.r=merge(l.r,r);update(l);return l;}
        else{r.l=merge(l,r.l);update(r);return r;}
    }

    static Node insert(Node t, int key){Node[] s=split(t,key);return merge(merge(s[0],new Node(key)),s[1]);}
    static Node delete(Node t, int key){
        if(t==null)return null;
        if(key<t.key){t.l=delete(t.l,key);update(t);return t;}
        if(key>t.key){t.r=delete(t.r,key);update(t);return t;}
        return merge(t.l,t.r);
    }

    static void inorder(Node t){if(t!=null){inorder(t.l);System.out.print(t.key+" ");inorder(t.r);}}

    public static void main(String[] args) {
        Node root=null;
        for(int v:new int[]{5,2,8,1,4,7,9})root=insert(root,v);
        inorder(root);System.out.println();
        root=delete(root,5);
        inorder(root);System.out.println();
        System.out.println("Size: "+size(root));
    }
}
