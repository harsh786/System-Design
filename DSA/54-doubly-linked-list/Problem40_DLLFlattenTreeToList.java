public class Problem40_DLLFlattenTreeToList {
    static class TreeNode{int val;TreeNode left,right;TreeNode(int v){val=v;}}
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static Node head,prev2;
    
    static Node treeToDoublyList(TreeNode root) {
        if(root==null)return null;
        head=null;prev2=null;
        inorder(root);
        return head;
    }
    
    static void inorder(TreeNode node){
        if(node==null)return;
        inorder(node.left);
        Node n=new Node(node.val);
        if(prev2==null)head=n;
        else{prev2.next=n;n.prev=prev2;}
        prev2=n;
        inorder(node.right);
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        TreeNode root=new TreeNode(4);root.left=new TreeNode(2);root.right=new TreeNode(6);
        root.left.left=new TreeNode(1);root.left.right=new TreeNode(3);
        print(treeToDoublyList(root)); // 1 2 3 4 6
    }
}
